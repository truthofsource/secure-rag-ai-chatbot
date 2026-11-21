import json
from pathlib import Path
import tempfile
import unittest
import uuid
from rag_project.pipeline import Library, Principal, answer, azure_answer, chunks, terms
from rag_project.runtime import Ledger, Stopped, digest


class RagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.library = Library(self.folder / "library.db")
        self.ledger = Ledger(self.folder / "usage.db")
        self.general = self.source(
            "general",
            ["Caregiver", "Admin"],
            "General",
            "Attendance: report missed clock events to a supervisor.",
        )
        self.restricted = self.source(
            "restricted",
            ["Admin"],
            "Restricted",
            "HR packet: restricted document review belongs to Admin.",
        )
        self.user = Principal(
            "tenant-a", "fictional-caregiver", frozenset(["Caregiver"])
        )
        self.admin = Principal("tenant-a", "fictional-admin", frozenset(["Admin"]))
        self.rid = str(uuid.uuid4())

    def tearDown(self):
        self.library.close()
        self.ledger.close()
        self.tmp.cleanup()

    def source(self, sid, roles, kind, text):
        path = self.folder / (sid + ".txt")
        path.write_text(text, encoding="utf-8")
        manifest = {
            "tenant": "tenant-a",
            "id": sid,
            "title": sid,
            "classification": kind,
            "roles": roles,
            "ai_allowed": True,
            "ocr_allowed": False,
            "file": str(path),
            "reviewed_sha256": digest(path.read_bytes()),
        }
        self.library.index(manifest)
        return manifest

    def ask(self, model, principal=None, **kwargs):
        return answer(
            self.library,
            principal or self.user,
            "attendance",
            self.ledger,
            self.rid,
            model,
            estimate_micro=100,
            get_token=kwargs.get("get_token", lambda: "fake-token"),
        )

    def test_general_reachable_restricted_denied(self):
        self.assertTrue(self.library.search(self.user, "attendance"))
        self.assertEqual([], self.library.search(self.user, "restricted"))
        self.assertEqual(
            "restricted", self.library.search(self.admin, "restricted")[0]["id"]
        )

    def test_tenant_isolation(self):
        stranger = Principal("tenant-b", "other", frozenset(["Admin"]))
        self.assertEqual([], self.library.search(stranger, "attendance"))

    def test_no_evidence_no_model_or_reservation(self):
        result = answer(
            self.library,
            self.user,
            "nonexistenttopic",
            self.ledger,
            self.rid,
            lambda *a: self.fail("No model allowed"),
            estimate_micro=100,
            get_token=lambda: self.fail("No token allowed"),
        )
        self.assertEqual([], result["citations"])
        self.assertEqual(
            0, self.ledger.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
        )

    def test_valid_cited_answer(self):
        result = self.ask(
            lambda *a: {"answer": "Report missed clock events.", "citations": ["C1"]}
        )
        self.assertEqual(["C1"], result["citations"])
        self.assertEqual("completed", self.ledger.get(self.rid)["state"])

    def test_invalid_citation_is_not_disclosed(self):
        with self.assertRaises(Stopped):
            self.ask(lambda *a: {"answer": "Claim", "citations": ["C999"]})
        self.assertEqual("unknown", self.ledger.get(self.rid)["state"])

    def test_uncited_claim_is_not_disclosed(self):
        with self.assertRaises(Stopped):
            self.ask(lambda *a: {"answer": "An unsupported claim", "citations": []})

    def test_withdraw_during_model_call_denies_output(self):
        def model(*a):
            self.library.withdraw("tenant-a", "general")
            return {"answer": "Report to supervisor", "citations": ["C1"]}

        with self.assertRaises(Stopped):
            self.ask(model)

    def test_uncited_context_is_also_rechecked(self):
        self.source(
            "general2",
            ["Caregiver"],
            "General",
            "Attendance notices are staff instructions.",
        )

        def model(*a):
            self.library.withdraw("tenant-a", "general2")
            return {"answer": "Report to supervisor", "citations": ["C1"]}

        with self.assertRaises(Stopped):
            self.ask(model)

    def test_file_changed_after_indexing_denies_search(self):
        Path(self.general["file"]).write_text("Changed content", encoding="utf-8")
        with self.assertRaises(Stopped):
            self.library.search(self.user, "attendance")

    def test_new_revision_invalidates_stale_evidence(self):
        stale = self.library.search(self.user, "attendance")[0]
        self.library.index(self.general)
        with self.assertRaises(Stopped):
            self.library.check(self.user, stale)

    def test_ai_permission_is_separate_from_read(self):
        changed = dict(self.general, ai_allowed=False)
        self.library.index(changed)
        self.assertTrue(self.library.search(self.user, "attendance"))
        with self.assertRaises(Stopped):
            self.ask(lambda *a: self.fail("No AI permission"))
        self.assertEqual(
            0, self.ledger.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
        )

    def test_invalid_audience_and_boolean_rejected(self):
        for changed in [
            dict(self.general, classification="Restricted"),
            dict(self.general, ai_allowed="false"),
        ]:
            with self.assertRaises(Stopped):
                self.library.index(changed)

    def test_whole_words_no_substring_matching(self):
        self.assertNotIn("attend", terms("attendance"))
        self.assertEqual([], self.library.search(self.user, "attend"))
        self.assertEqual({"café"}, terms("cafe\u0301"))

    def test_chunks_bounded_without_cutting_words(self):
        result = list(chunks(" ".join(["abcdefghij"] * 800)))
        self.assertGreater(len(result), 1)
        self.assertTrue(all(len(c) <= 1200 for c in result))
        with self.assertRaises(Stopped):
            list(chunks("x" * 1201))

    def test_token_failure_not_sent_timeout_unknown(self):
        def fail():
            raise Stopped("No credential")

        with self.assertRaises(Stopped):
            self.ask(lambda *a: self.fail("Must not send"), get_token=fail)
        self.assertEqual("not_sent", self.ledger.get(self.rid)["state"])
        self.rid = str(uuid.uuid4())

        def timeout(*a):
            raise TimeoutError()

        with self.assertRaises(TimeoutError):
            self.ask(timeout)
        self.assertEqual("unknown", self.ledger.get(self.rid)["state"])

    def test_azure_payload_and_no_hidden_paid_retries(self):
        calls = []

        def http(method, url, data, bearer):
            payload = json.loads(data)
            calls.append(url)
            self.assertFalse(payload["store"])
            self.assertEqual(500, payload["max_tokens"])
            self.assertIn("untrusted data", payload["messages"][0]["content"])
            return (
                200,
                {},
                json.dumps(
                    {
                        "choices": [
                            {
                                "finish_reason": "stop",
                                "message": {
                                    "content": '{"answer":"Example","citations":["C1"]}'
                                },
                            }
                        ]
                    }
                ).encode(),
            )

        result = azure_answer(
            "question",
            [],
            "https://fictional-model.openai.azure.com",
            "chat-deployment",
            bearer="fake",
            http=http,
        )
        self.assertEqual(["C1"], result["citations"])
        self.assertEqual(1, len(calls))

    def test_ocr_hash_and_permission_required(self):
        with self.assertRaises(Stopped):
            self.library.index(
                self.general,
                {
                    "method": "azure-document-intelligence-prebuilt-read",
                    "source_sha256": self.general["reviewed_sha256"],
                    "pages": [{"page": 1, "text": "ocr"}],
                },
            )
        with self.assertRaises(Stopped):
            self.library.index(
                dict(self.general, ocr_allowed=True),
                {
                    "method": "fictional-offline-fixture",
                    "source_sha256": None,
                    "pages": [],
                },
            )

    def scan_fixture(self):
        path = self.folder / "scan.pdf"
        path.write_bytes(b"%PDF-fictional transport fixture")
        manifest = dict(
            self.general,
            id="scan",
            file=str(path),
            reviewed_sha256=digest(path.read_bytes()),
            ocr_allowed=True,
        )
        result = {
            "schema": 1,
            "method": "azure-document-intelligence-prebuilt-read",
            "source_sha256": manifest["reviewed_sha256"],
            "pages": [{"page": 2, "text": "Scanned attendance instructions."}],
        }
        return manifest, result

    def test_approved_ocr_import_preserves_page_and_hash(self):
        manifest, result = self.scan_fixture()
        self.library.index(manifest, result)
        evidence = [
            p for p in self.library.search(self.user, "scanned") if p["id"] == "scan"
        ]
        self.assertEqual(2, evidence[0]["page"])
        self.assertEqual(1, evidence[0]["revision"])

    def test_bad_ocr_page_rejects_without_replacing_previous_revision(self):
        manifest, result = self.scan_fixture()
        self.library.index(manifest, result)
        result["pages"].append({"page": 2, "text": "Duplicate"})
        with self.assertRaises(Stopped):
            self.library.index(manifest, result)
        self.assertEqual(1, self.library.search(self.user, "scanned")[0]["revision"])

    def test_null_nontext_or_malformed_ocr_page_rejected(self):
        manifest, result = self.scan_fixture()
        for page in [
            {"page": None, "text": "Attendance"},
            {"page": 1, "text": []},
            {"page": True, "text": "Attendance"},
            {"text": "Attendance"},
        ]:
            result["pages"] = [page]
            with self.assertRaises(Stopped):
                self.library.index(manifest, result)

    def test_ocr_schema_and_original_format_required(self):
        manifest, result = self.scan_fixture()
        for version in [None, True, 2]:
            changed = dict(result, schema=version)
            with self.assertRaises(Stopped):
                self.library.index(manifest, changed)
        result["source_sha256"] = self.general["reviewed_sha256"]
        with self.assertRaises(Stopped):
            self.library.index(dict(self.general, ocr_allowed=True), result)

    def test_manifest_structure_and_duplicate_roles_rejected(self):
        for changed in [
            [],
            {},
            dict(self.general, roles="Admin"),
            dict(self.general, roles=["Admin", "Admin"]),
            dict(self.general, roles=[["Admin"]]),
        ]:
            with self.assertRaises(Stopped):
                self.library.index(changed)

    def test_numeric_reference_is_searchable(self):
        self.source(
            "reference",
            ["Caregiver"],
            "General",
            "Retention reference 2026 applies to fictional instructions.",
        )
        self.assertEqual("reference", self.library.search(self.user, "2026")[0]["id"])

    def test_search_rechecks_before_disclosing_selected_passages(self):
        from unittest.mock import patch

        original = self.library.check
        changed = False

        def check(principal, evidence, **kwargs):
            nonlocal changed
            original(principal, evidence, **kwargs)
            if not changed:
                changed = True
                self.library.withdraw("tenant-a", "general")

        with patch.object(self.library, "check", side_effect=check):
            with self.assertRaises(Stopped):
                self.library.search(self.user, "attendance")

    def test_unrelated_missing_source_does_not_block_matching_evidence(self):
        Path(self.restricted["file"]).unlink()
        self.assertTrue(self.library.search(self.admin, "attendance"))

    def test_matching_missing_source_still_blocks_disclosure(self):
        Path(self.general["file"]).unlink()
        with self.assertRaises(Stopped):
            self.library.search(self.user, "attendance")

    def test_import_rejects_unpaired_unicode_without_partial_revision(self):
        manifest, result = self.scan_fixture()
        result["pages"] = [{"page": 1, "text": "\ud800"}]
        with self.assertRaises(Stopped):
            self.library.index(manifest, result)
        self.assertEqual(
            0,
            self.library.db.execute(
                "SELECT COUNT(*) FROM sources WHERE id='scan'"
            ).fetchone()[0],
        )

    def test_invalid_native_encoding_preserves_revision(self):
        path = Path(self.general["file"])
        path.write_bytes(b"\xff\xfeinvalid")
        changed = dict(self.general, reviewed_sha256=digest(path.read_bytes()))
        with self.assertRaisesRegex(Stopped, "not valid UTF-8"):
            self.library.index(changed)
        self.assertEqual(
            1,
            self.library.db.execute(
                "SELECT revision FROM sources WHERE id='general'"
            ).fetchone()[0],
        )

    def test_invalid_model_unicode_is_held_and_not_disclosed(self):
        with self.assertRaisesRegex(Stopped, "invalid Unicode"):
            self.ask(lambda *a: {"answer": "Invalid \ud800", "citations": ["C1"]})
        self.assertEqual("unknown", self.ledger.get(self.rid)["state"])

    def test_unsearchable_replacement_does_not_publish(self):
        path = Path(self.general["file"])
        for content in (" \n\t", "!!! ...", "x" * 129):
            path.write_text(content, encoding="utf-8")
            changed = dict(self.general, reviewed_sha256=digest(path.read_bytes()))
            with (
                self.subTest(content=content),
                self.assertRaisesRegex(Stopped, "No searchable text"),
            ):
                self.library.index(changed)
            self.assertEqual(
                1,
                self.library.db.execute(
                    "SELECT revision FROM sources WHERE id='general'"
                ).fetchone()[0],
            )
