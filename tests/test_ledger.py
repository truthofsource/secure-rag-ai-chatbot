import json
from pathlib import Path
import tempfile
import unittest
import uuid
from rag_project.runtime import Ledger, Stopped, endpoint


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "usage.db"
        self.ledger = Ledger(self.path, 100)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def reserve(self, estimate=10):
        rid = str(uuid.uuid4())
        self.ledger.reserve(rid, "test-operator", "fixture-hash", estimate)
        return rid

    def test_duplicate_request_never_resubmits(self):
        rid = self.reserve()
        self.ledger.settle(rid, "completed")
        with self.assertRaises(Stopped):
            self.ledger.reserve(rid, "test-operator", "other", 10)

    def test_unknown_survives_reopen_and_blocks_another_caller(self):
        rid = self.reserve()
        self.ledger.settle(rid, "unknown")
        other = Ledger(self.path, 100)
        try:
            with self.assertRaises(Stopped):
                other.reserve(str(uuid.uuid4()), "other-operator", "x", 10)
        finally:
            other.close()

    def test_budget_denial_occurs_before_provider(self):
        rid = self.reserve(95)
        self.ledger.settle(rid, "completed")
        with self.assertRaises(Stopped):
            self.reserve(6)

    def test_not_sent_cost_zero_but_still_counts_daily(self):
        for _ in range(20):
            rid = self.reserve(100)
            self.ledger.settle(rid, "not_sent")
        with self.assertRaises(Stopped):
            self.reserve(1)

    def test_no_invalid_endpoint_or_redirect_target(self):
        for value in [
            "http://test.openai.azure.com",
            "https://example.com",
            "https://test.openai.azure.com/path",
            "https://test.openai.azure.com@evil.test",
        ]:
            with self.assertRaises(Stopped):
                endpoint(value, "openai.azure.com")

    def test_bad_request_id_does_not_create_record(self):
        with self.assertRaises(Stopped):
            self.ledger.reserve("not-a-uuid", "actor", "x", 1)
        self.assertEqual(
            0, self.ledger.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0]
        )

    def test_uppercase_uuid_settlement_finds_canonical_record(self):
        rid = str(uuid.uuid4()).upper()
        self.ledger.reserve(rid, "actor", "hash", 10)
        self.ledger.receipt(rid, "saved-operation")
        self.ledger.settle(rid, "completed")
        self.assertEqual("completed", self.ledger.get(rid)["state"])
        self.assertEqual("saved-operation", self.ledger.get(rid)["operation"])

    def test_two_connections_race_only_one_reservation_wins(self):
        import concurrent.futures
        import threading

        barrier = threading.Barrier(2)

        def attempt(actor):
            ledger = Ledger(self.path, 100)
            try:
                barrier.wait(timeout=5)
                try:
                    ledger.reserve(str(uuid.uuid4()), actor, "hash", 10)
                    return "admitted"
                except Stopped:
                    return "denied"
            finally:
                ledger.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["one", "two"]))
        self.assertEqual(["admitted", "denied"], sorted(results))

    def test_unknown_cannot_be_released_as_not_sent(self):
        rid = self.reserve()
        self.ledger.settle(rid, "unknown")
        with self.assertRaises(Stopped):
            self.ledger.settle(rid, "not_sent")
        self.assertEqual("unknown", self.ledger.get(rid)["state"])

    def test_completed_result_and_operation_are_immutable(self):
        rid = self.reserve()
        self.ledger.receipt(rid, "operation-one")
        self.ledger.settle(rid, "completed", {"pages": ["original"]})
        with self.assertRaises(Stopped):
            self.ledger.settle(rid, "completed", {"pages": ["replacement"]})
        with self.assertRaises(Stopped):
            self.ledger.receipt(rid, "operation-two")
        self.assertEqual(
            {"pages": ["original"]}, json.loads(self.ledger.get(rid)["result"])
        )
        self.assertEqual("operation-one", self.ledger.get(rid)["operation"])

    def test_not_sent_is_terminal(self):
        rid = self.reserve()
        self.ledger.settle(rid, "not_sent")
        with self.assertRaises(Stopped):
            self.ledger.settle(rid, "completed")
        with self.assertRaises(Stopped):
            self.ledger.receipt(rid, "operation-late")

    def test_repeated_same_completion_does_not_duplicate_audit(self):
        rid = self.reserve()
        self.ledger.settle(rid, "completed", {"result": "same"})
        self.ledger.settle(rid, "completed", {"result": "same"})
        self.assertEqual(
            1,
            self.ledger.db.execute(
                "SELECT COUNT(*) FROM audit WHERE request_id=? AND event='completed'",
                (rid,),
            ).fetchone()[0],
        )

    def test_actual_file_read_is_bounded(self):
        from rag_project.runtime import read_file

        source = Path(self.temp.name) / "large.txt"
        source.write_bytes(b"x" * 11)
        with self.assertRaises(Stopped):
            read_file(source, 10)
        self.assertEqual(b"x" * 11, read_file(source, 11))

    def test_saved_provider_operation_cannot_be_called_not_sent(self):
        rid = self.reserve()
        self.ledger.receipt(rid, "provider-operation")
        with self.assertRaises(Stopped):
            self.ledger.settle(rid, "not_sent")
        self.assertEqual("reserved", self.ledger.get(rid)["state"])
