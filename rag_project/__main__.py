import argparse
import json
import os
from pathlib import Path
from .pipeline import Library, Principal, answer, azure_answer
from .runtime import Ledger, Stopped, digest, read_file


def main():
    parser = argparse.ArgumentParser(
        description="Trusted local operator demo, NOT a public API or identity validator."
    )
    parser.add_argument("--db", default="work/library.db")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    index = sub.add_parser("index")
    index.add_argument("manifest")
    index.add_argument("--ocr-result")
    index.add_argument("--reviewed-input", action="store_true")
    for command in ("search", "answer"):
        p = sub.add_parser(command)
        p.add_argument("question")
        p.add_argument(
            "--role",
            choices=["Admin", "HR", "Payroll", "Supervisor", "Caregiver"],
            required=True,
        )
        p.add_argument("--tenant", default="fictional")
        p.add_argument("--actor", default="local-operator")
        if command == "answer":
            p.add_argument("--request-id", required=True)
    drop = sub.add_parser("withdraw")
    drop.add_argument("source_id")
    drop.add_argument("--tenant", default="fictional")
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    library = Library(args.db)
    try:
        if args.command == "demo":
            for sid, roles, kind in [
                (
                    "general",
                    ["Admin", "HR", "Payroll", "Supervisor", "Caregiver"],
                    "General",
                ),
                ("restricted", ["Admin", "HR"], "Restricted"),
            ]:
                source = Path("examples/" + sid + ".txt").resolve()
                library.index(
                    {
                        "tenant": "fictional",
                        "id": sid,
                        "title": sid.title() + " instructions",
                        "file": str(source),
                        "classification": kind,
                        "roles": roles,
                        "ai_allowed": True,
                        "ocr_allowed": False,
                        "reviewed_sha256": digest(read_file(source)),
                    }
                )
            print("Fictional sources indexed; no Azure or model calls made.")
            return
        if args.command == "index":
            if not args.reviewed_input:
                raise Stopped(
                    "Only a trusted operator may index reviewed input. Complete the file-safety and audience review first."
                )
            manifest_path = Path(args.manifest).resolve()
            manifest = json.loads(read_file(manifest_path, 64 * 1024).decode("utf-8"))
            manifest["file"] = str((manifest_path.parent / manifest["file"]).resolve())
            pages = (
                json.loads(read_file(args.ocr_result, 8 * 1024 * 1024).decode("utf-8"))
                if args.ocr_result
                else None
            )
            print("Published revision", library.index(manifest, pages))
            return
        if args.command == "withdraw":
            library.withdraw(args.tenant, args.source_id)
            print("Source withdrawn from new searches; original retained.")
            return
        principal = Principal(args.tenant, args.actor, frozenset([args.role]))
        if args.command == "search":
            print(json.dumps(library.search(principal, args.question), indent=2))
            return
        if os.environ.get("ALLOW_AZURE_CALLS") != "yes":
            raise Stopped(
                "Live answers are Off. Local search remains available without a model."
            )
        base, deployment = (
            os.environ["AZURE_OPENAI_ENDPOINT"],
            os.environ["AZURE_OPENAI_DEPLOYMENT"],
        )
        # Validate deployment/endpoint before admitting a paid operation.
        from .runtime import endpoint
        import re

        endpoint(base, "openai.azure.com")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", deployment):
            raise Stopped("Invalid Azure deployment name.")
        ledger = Ledger(
            Path(args.db).with_name("usage.db"),
            int(os.environ.get("MONTHLY_PROCESSING_MICRO", "3000000")),
        )
        try:
            result = answer(
                library,
                principal,
                args.question,
                ledger,
                args.request_id,
                lambda q, p, t: azure_answer(q, p, base, deployment, bearer=t),
                estimate_micro=int(os.environ["ANSWER_ESTIMATE_MICRO"]),
            )
            print(json.dumps(result, indent=2))
        finally:
            ledger.close()
    finally:
        library.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "Stopped:",
            (
                str(error)
                if isinstance(error, Stopped)
                else "Check configuration, UTF-8 input, source files and local permissions. No automatic retry was made."
            ),
        )
        raise SystemExit(2)
