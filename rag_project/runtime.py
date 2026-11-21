"""Local runtime; no hosted identity boundary is provided here."""

from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import sqlite3
import urllib.error
import urllib.request
import uuid
from pathlib import Path


class Stopped(RuntimeError):
    """Safe error text suitable for the local CLI; excludes provider response bodies."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_file(path: str | Path, limit: int = 10 * 1024 * 1024) -> bytes:
    """Bound the actual read, rather than trusting a preceding file-size check."""
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError:
        raise Stopped(
            "The local file is missing or unreadable. Check its path and permissions before retrying."
        ) from None
    if len(data) > limit:
        raise Stopped(
            "The local file exceeds the configured byte limit. No partial file was accepted."
        )
    return data


def canonical_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise Stopped(
            "Use a UUID request ID; do not retry uncertain work with a new ID."
        ) from None


def endpoint(value: str, suffix: str) -> str:
    if not re.fullmatch(
        r"https://[a-z0-9][a-z0-9-]{1,62}\." + re.escape(suffix) + r"/?", value
    ):
        raise Stopped(
            "Configure an exact Azure HTTPS resource endpoint, without paths or query strings."
        )
    return value.rstrip("/")


def token() -> str:
    # Optional dependency is imported only for explicitly selected live execution.
    from azure.identity import DefaultAzureCredential

    with DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    ) as credential:
        return credential.get_token("https://ai.azure.com/.default").token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(method: str, url: str, data: bytes | None, bearer: str, timeout=25):
    """One HTTP attempt. Never follow redirects or automatically retry a paid POST."""
    headers = {"Authorization": "Bearer " + bearer, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            req, timeout=timeout
        ) as response:
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise Stopped(
                    "Provider response exceeded the local 4 MiB limit; inspect the held request."
                )
            return response.status, dict(response.headers), body
    except urllib.error.HTTPError as error:
        error.close()
        raise Stopped(
            f"Azure returned HTTP {error.code}. Check access, deployment, quota and resource availability; do not blindly resend."
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise Stopped(
            "Azure could not be reached or the request timed out. Resources or private paths may be unavailable; submitted work remains held."
        ) from None


class Ledger:
    """Atomic, durable local admission. One ledger must be shared by all local callers."""

    def __init__(self, path: str | Path, monthly_micro: int = 3_000_000):
        if type(monthly_micro) is not int or monthly_micro <= 0:
            raise Stopped(
                "The monthly processing allowance must be a positive integer in microdollars."
            )
        self.limit = monthly_micro
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS usage (
            request_id TEXT PRIMARY KEY, actor TEXT NOT NULL, created TEXT NOT NULL,
            fingerprint TEXT NOT NULL, estimate INTEGER NOT NULL,
            state TEXT NOT NULL, operation TEXT, result TEXT);
          CREATE TABLE IF NOT EXISTS audit (
            at TEXT NOT NULL, event TEXT NOT NULL, request_id TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    def reserve(self, request_id, actor, fingerprint, estimate):
        request_id = canonical_id(request_id)
        if not actor or len(actor) > 120 or type(estimate) is not int or estimate <= 0:
            raise Stopped("Invalid actor or processing estimate.")
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute(
                "SELECT 1 FROM usage WHERE request_id=?", (request_id,)
            ).fetchone():
                raise Stopped(
                    "This request ID already exists. Inspect or resume its saved operation; no new submission was made."
                )
            if self.db.execute(
                "SELECT 1 FROM usage WHERE state IN ('reserved','unknown')"
            ).fetchone():
                raise Stopped(
                    "Another paid request is active or uncertain. Resolve that record before processing more files/questions."
                )
            count = self.db.execute(
                "SELECT COUNT(*) FROM usage WHERE actor=? AND substr(created,1,10)=?",
                (actor, now[:10]),
            ).fetchone()[0]
            spent = self.db.execute(
                "SELECT COALESCE(SUM(estimate),0) FROM usage WHERE substr(created,1,7)=? AND state != 'not_sent'",
                (now[:7],),
            ).fetchone()[0]
            if count >= 20 or spent + estimate > self.limit:
                raise Stopped(
                    "Daily reservation count or monthly processing allowance reached. No paid provider request was made."
                )
            self.db.execute(
                "INSERT INTO usage VALUES (?,?,?,?,?,?,NULL,NULL)",
                (request_id, actor, now, fingerprint, estimate, "reserved"),
            )
            self.db.execute(
                "INSERT INTO audit VALUES (?,?,?)", (now, "reserved", request_id)
            )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def get(self, request_id):
        row = self.db.execute(
            "SELECT * FROM usage WHERE request_id=?", (canonical_id(request_id),)
        ).fetchone()
        if row is None:
            raise Stopped("No saved request exists in this ledger.")
        return dict(row)

    def receipt(self, request_id, operation):
        request_id = canonical_id(request_id)
        if not isinstance(operation, str) or not operation or len(operation) > 16_384:
            raise Stopped(
                "Invalid operation receipt; preserve the request for investigation."
            )
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.get(request_id)
            if row["operation"] == operation:
                self.db.execute("COMMIT")
                return
            if row["operation"] is not None or row["state"] not in (
                "reserved",
                "unknown",
            ):
                raise Stopped(
                    "A saved operation receipt cannot be replaced or attached to terminal work."
                )
            self.db.execute(
                "UPDATE usage SET operation=? WHERE request_id=?",
                (operation, request_id),
            )
            self.db.execute(
                "INSERT INTO audit VALUES (?,?,?)",
                (
                    dt.datetime.now(dt.timezone.utc).isoformat(),
                    "receipt_saved",
                    request_id,
                ),
            )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def settle(self, request_id, state, result=None):
        request_id = canonical_id(request_id)
        if state not in ("not_sent", "completed", "unknown"):
            raise Stopped("Invalid usage outcome.")
        encoded = json.dumps(result) if result is not None else None
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.get(request_id)
            if row["state"] == state:
                if encoded is not None and encoded != row["result"]:
                    raise Stopped(
                        "A recorded result is immutable; inspect the original request instead of replacing it."
                    )
                self.db.execute("COMMIT")
                return
            if state == "not_sent" and row["operation"] is not None:
                raise Stopped(
                    "A saved provider operation proves submission; it cannot be released as not sent."
                )
            allowed = {
                "reserved": {"not_sent", "completed", "unknown"},
                "unknown": {"completed"},
            }
            if state not in allowed.get(row["state"], set()):
                raise Stopped(
                    "This usage transition would release uncertain work or change a terminal result; it was blocked."
                )
            self.db.execute(
                "UPDATE usage SET state=?, result=? WHERE request_id=?",
                (state, encoded, request_id),
            )
            self.db.execute(
                "INSERT INTO audit VALUES (?,?,?)",
                (dt.datetime.now(dt.timezone.utc).isoformat(), state, request_id),
            )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    # Completed work retains its conservative estimate, not a claimed Azure bill.
    # Unknown holds never expire automatically. No unsafe "clear hold" command.
