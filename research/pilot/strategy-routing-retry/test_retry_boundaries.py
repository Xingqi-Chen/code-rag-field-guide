"""Offline retry-ledger boundaries; all writes and transports are temporary/fake.

Uses the frozen inherited manifest and successful old responses read-only. This
tests execution boundaries, not model quality or the official DRIFT algorithm.
Run: PYTHONDONTWRITEBYTECODE=1 python3 -S <this file> -v
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("retry_boundaries_subject", HERE / "bounded.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def forbid_network_and_credentials(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "http.client.connect", "urllib.Request"}:
        raise RuntimeError("offline boundary test forbids network")
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if "credentials" in path.name.lower() or path.suffix == ".env":
            raise RuntimeError("offline boundary test forbids credential reads")
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing and path.is_relative_to(b.ROOT / ".cache"):
            raise RuntimeError("offline boundary test forbids original cache writes")


sys.addaudithook(forbid_network_and_credentials)


class Tokenizer:
    """Deterministic stand-in: new reservations only; old token carry is exact."""
    def encode(self, text):
        return range((len(text) + 3) // 4)


def success(service="generation", text="Synthetic completed reply"):
    if service == "generation":
        response = {"model": b.MODEL, "choices": [{"finish_reason": "stop", "message": {"content": text}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25}}
    else:
        response = {"model": b.EMBED, "data": [{"index": 0, "embedding": [0.0] * 3072}],
                    "usage": {"prompt_tokens": 5, "total_tokens": 5}}
    return {"http_status": 200, "request_dispatched": True, "response": response}


def failure(status=503, category="model_related", dispatched=True):
    return {"http_status": status, "error_category": category, "request_dispatched": dispatched}


class FakeTransport:
    def __init__(self, replies=()):
        self.replies = list(replies)
        self.calls = []

    def check_authorization(self):
        raise b.Halt("test_live_launch_forbidden", fatal=True)

    def dispatch(self, request, response, seconds):
        payload = b.read(request)
        state = b.read(request.parent / "summary.json")
        event = state["events"][-1]
        assert event["status"] == "reserved_before_dispatch"
        assert request.name == f'request-{event["sequence"]:02}.json'
        assert event["key"] == b.digest(payload)
        self.calls.append((payload, seconds))
        action = self.replies.pop(0) if self.replies else success(payload["service"])
        if callable(action):
            return action(request, response)
        return copy.deepcopy(action)


class RetryBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.old = b.inheritance()
        cls.protected = {b.ROOT / name: sha for name, sha in cls.manifest["files"].items()}
        cls.protected[b.ROOT / cls.manifest["old_run"] / "summary.json"] = cls.manifest["old_summary_sha256"]
        cls.protected[HERE / "inherited-manifest.json"] = b.file_sha(HERE / "inherited-manifest.json")

    @classmethod
    def tearDownClass(cls):
        for path, sha in cls.protected.items():
            if b.file_sha(path) != sha:
                raise AssertionError("an inherited input changed during the offline tests")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="drift-retry-boundaries-")
        self.addCleanup(self.tmp.cleanup)
        self.enc = Tokenizer()
        self.serial = 0

    def runtime(self, replies=(), limits=None):
        self.serial += 1
        transport = FakeTransport(replies)
        waits = []
        run = b.Runtime(Path(self.tmp.name) / str(self.serial), transport, self.enc, self.enc,
                        create=True, synthetic=True, limits=limits, wait=waits.append)
        self.addCleanup(run.close)
        return run, transport, waits

    def inherited_key(self, stage, qid="Q08"):
        return next(key for key, record in self.manifest["cells"][qid + ":routed_graphrag"]["requests"].items()
                    if record["stage"] == stage)

    def inherited_request(self, run, cell, stage):
        key = self.inherited_key(stage, cell.data["qid"])
        record = self.old["requests"][key]
        return run.request(cell.key, record["service"], copy.deepcopy(record["body"]), stage)

    def reopen(self, run, transport=None):
        run.close()
        new = b.Runtime(run.directory, transport or FakeTransport(), self.enc, self.enc,
                        synthetic=True, limits=run.limits, wait=lambda _: None)
        self.addCleanup(new.close)
        return new

    def assert_resume_rejects(self, mutate):
        run, transport, _ = self.runtime()
        cell = run.cell("Q08", "routed_graphrag", "drift")
        mutate(run, cell)
        run.persist()
        run.close()
        with self.assertRaises(b.Halt):
            self.reopen(run, transport)
        self.assertEqual(transport.calls, [])

    def test_manifest_exactly_matches_original_failed_cells(self):
        self.assertEqual(self.old["counts"], b.CARRY)
        self.assertEqual(set(self.manifest["cells"]), {qid + ":routed_graphrag" for qid in b.QIDS})
        self.assertEqual(sum(c["generation_input_tokens"] for c in self.manifest["cells"].values()), 20219)
        for cell_key, carry in self.manifest["cells"].items():
            oldcell = self.old["cells"][cell_key]
            self.assertEqual(oldcell["status"], "failed")
            self.assertEqual(carry["generation_input_tokens"], oldcell["generation_input_tokens"])
            self.assertEqual(set(carry["requests"]), set(oldcell["requests"]))
            for key, prior in carry["requests"].items():
                record = self.old["requests"][key]
                self.assertEqual(prior["old_events"], record["events"])
                self.assertEqual(prior["prior_attempts"], len(record["events"]))
                self.assertEqual(prior["prior_attempts"], 1)
                self.assertEqual({"stage": prior["stage"], "service": prior["service"]}, oldcell["requests"][key])
                self.assertEqual(prior["complete"], bool(record.get("completed_response")))
                self.assertEqual(key, b.digest({"service": record["service"], "body": record["body"]}))

    def test_carry_and_six_cell_old_input_are_not_reset(self):
        run, transport, _ = self.runtime()
        for qid in b.QIDS:
            cell = run.cell(qid, "routed_graphrag", "drift")
            expected = self.manifest["cells"][cell.key]["generation_input_tokens"]
            self.assertEqual(cell.data["generation_input_tokens"], expected)
            self.assertEqual(cell.data["prior_generation_input_tokens"], expected)
        self.assertEqual(run.state["counts"], b.CARRY)
        self.assertEqual(run.state["events"], [])
        self.assertEqual(transport.calls, [])
        self.reopen(run).verify_ledger()

    def test_only_six_exact_drift_cells_are_authorized(self):
        for args in [("Q01", "routed_graphrag", "drift"), ("Q08", "bm25", "drift"),
                     ("Q08", "routed_graphrag", "local")]:
            run, transport, _ = self.runtime()
            with self.assertRaisesRegex(b.Halt, "retry_cell_not_authorized"):
                run.cell(*args)
            self.assertEqual(transport.calls, [])

    def test_live_gate_precedes_directory_creation(self):
        path = Path(self.tmp.name) / "not-live"
        with self.assertRaisesRegex(b.Halt, "test_live_launch_forbidden"):
            b.Runtime(path, FakeTransport(), self.enc, self.enc, create=True)
        self.assertFalse(path.exists())

    def test_all_twelve_successful_old_replies_replay_without_new_charge(self):
        run, transport, _ = self.runtime()
        for qid in b.QIDS:
            cell = run.cell(qid, "routed_graphrag", "drift")
            for stage in ("hyde", "query_embedding"):
                first = self.inherited_request(run, cell, stage)
                second = self.inherited_request(run, cell, stage)
                self.assertEqual(first, second)
                self.assertTrue(cell.data["uses"][-1]["cache"])
                self.assertEqual(cell.data["uses"][-1]["origin_run"], self.manifest["old_run"])
        self.assertEqual(run.state["counts"], b.CARRY)
        self.assertEqual(run.state["events"], [])
        self.assertEqual(transport.calls, [])
        self.reopen(run).verify_ledger()

    def test_changed_inherited_generation_body_or_stage_is_rejected(self):
        for stage in ("hyde", "primer"):
            run, transport, _ = self.runtime()
            cell = run.cell("Q08", "routed_graphrag", "drift")
            body = copy.deepcopy(self.old["requests"][self.inherited_key(stage)]["body"])
            body["input"][0]["content"][0]["text"] += " changed"
            with self.assertRaisesRegex(b.Halt, "inherited_generation_body_changed"):
                run.request(cell.key, "generation", body, stage)
            self.assertEqual(transport.calls, [])
        run, transport, _ = self.runtime()
        cell = run.cell("Q08", "routed_graphrag", "drift")
        body = self.old["requests"][self.inherited_key("hyde")]["body"]
        with self.assertRaisesRegex(b.Halt, "request_stage_changed"):
            run.request(cell.key, "generation", body, "primer")
        self.assertEqual(transport.calls, [])

    def test_new_embedding_before_exact_primer_is_rejected(self):
        run, transport, _ = self.runtime()
        cell = run.cell("Q08", "routed_graphrag", "drift")
        with self.assertRaisesRegex(b.Halt, "inherited_embedding_body_changed"):
            cell.embed(["changed HyDE embedding text"])
        self.assertEqual(transport.calls, [])

    def test_primer_has_only_two_remaining_attempts_with_shared_delay(self):
        run, transport, waits = self.runtime([failure(), failure(None, "worker_wall_timeout")])
        cell = run.cell("Q08", "routed_graphrag", "drift")
        with self.assertRaises(b.Halt):
            self.inherited_request(run, cell, "primer")
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(waits, [15])
        record = run.state["requests"][self.inherited_key("primer")]
        self.assertEqual(record["prior_attempts"] + len(record["events"]), 3)
        self.assertEqual(run.state["counts"]["generation_reservations"], b.CARRY["generation_reservations"] + 2)
        with self.assertRaises(b.Halt):
            self.inherited_request(run, cell, "primer")
        self.assertEqual(len(transport.calls), 2)
        self.reopen(run).verify_ledger()

    def test_successful_new_primer_is_exact_cached_and_resume_keeps_counts(self):
        run, transport, _ = self.runtime()
        cell = run.cell("Q08", "routed_graphrag", "drift")
        first = self.inherited_request(run, cell, "primer")
        counts = copy.deepcopy(run.state["counts"])
        self.assertEqual(self.inherited_request(run, cell, "primer"), first)
        self.assertEqual(len(transport.calls), 1)
        resumed = self.reopen(run)
        self.assertEqual(self.inherited_request(resumed, resumed.cell("Q08", "routed_graphrag", "drift"), "primer"), first)
        self.assertEqual(resumed.state["counts"], counts)
        self.assertEqual(resumed.transport.calls, [])

    def test_old_per_cell_input_is_included_in_retry_limit(self):
        body = self.old["requests"][self.inherited_key("primer")]["body"]
        tokens = sum(len(self.enc.encode(m["content"][0]["text"])) for m in body["input"])
        limits = {**b.LIMITS, "cell_input": 3159 + tokens}
        run, transport, _ = self.runtime([failure()], limits=limits)
        cell = run.cell("Q08", "routed_graphrag", "drift")
        with self.assertRaisesRegex(b.Halt, "cell_input_limit"):
            self.inherited_request(run, cell, "primer")
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(cell.data["generation_input_tokens"], 3159 + tokens)
        self.assertEqual(run.state["counts"]["generation_input_tokens"], b.CARRY["generation_input_tokens"] + tokens)

    def test_global_generation_limit_counts_original_reservations(self):
        run, transport, _ = self.runtime(limits={**b.LIMITS, "generation_reservations": b.CARRY["generation_reservations"]})
        cell = run.cell("Q08", "routed_graphrag", "drift")
        with self.assertRaisesRegex(b.Halt, "generation_reservation_limit"):
            self.inherited_request(run, cell, "primer")
        self.assertEqual(transport.calls, [])
        self.assertEqual(run.state["counts"], b.CARRY)

    def test_embedding_limit_keeps_original_attempt_carry(self):
        run, transport, _ = self.runtime(limits={**b.LIMITS, "embedding_attempts": b.CARRY["embedding_attempts"]})
        cell = run.cell("Q08", "routed_graphrag", "drift")
        self.inherited_request(run, cell, "primer")
        with self.assertRaisesRegex(b.Halt, "embedding_attempt_limit"):
            cell.embed(["new Local search text"])
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(run.state["counts"]["embedding_attempts"], b.CARRY["embedding_attempts"])

    def test_decoder_failure_remains_single_dispatch_and_retains_usage(self):
        reply = failure(200, "responses_empty_or_multiple_messages")
        reply["transport_diagnostics"] = {"provider_usage": {"input_tokens": 44, "output_tokens": 7, "total_tokens": 51}}
        run, transport, _ = self.runtime([reply])
        cell = run.cell("Q08", "routed_graphrag", "drift")
        with self.assertRaisesRegex(b.Halt, "responses_empty_or_multiple_messages"):
            self.inherited_request(run, cell, "primer")
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(run.state["events"][0]["usage"], {"prompt_tokens": 44, "completion_tokens": 7, "total_tokens": 51})
        self.assertEqual(run.state["events"][0]["request_dispatched"], True)

    def test_non_dispatch_and_permission_failures_never_retry(self):
        for reply in [failure(dispatched=False), failure(401, "unclassified_http_error"), failure(503, "safety_related")]:
            run, transport, waits = self.runtime([reply])
            cell = run.cell("Q08", "routed_graphrag", "drift")
            with self.assertRaises(b.Halt):
                self.inherited_request(run, cell, "primer")
            self.assertEqual(len(transport.calls), 1)
            self.assertEqual(waits, [])

    def test_resume_rejects_counter_cell_token_and_prior_attempt_resets(self):
        mutations = [lambda r, c: r.state["counts"].update(generation_reservations=0),
                     lambda r, c: c.data.update(generation_input_tokens=0),
                     lambda r, c: c.data.update(prior_generation_input_tokens=0),
                     lambda r, c: r.state["requests"][self.inherited_key("primer")].update(prior_attempts=0)]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.assert_resume_rejects(mutation)

    def test_resume_rejects_removed_inherited_records_and_cell_metadata(self):
        mutations = [lambda r, c: r.state["requests"].pop(self.inherited_key("primer")),
                     lambda r, c: c.data["requests"].clear(),
                     lambda r, c: c.data.update(route="local"),
                     lambda r, c: c.data["requests"][self.inherited_key("hyde")].update(stage="primer")]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.assert_resume_rejects(mutation)

    def test_resume_rejects_changed_inherited_body_service_events_and_cache(self):
        mutations = [lambda r, c: r.state["requests"][self.inherited_key("primer")].update(body={}),
                     lambda r, c: r.state["requests"][self.inherited_key("primer")].update(service="embedding"),
                     lambda r, c: r.state["requests"][self.inherited_key("primer")].update(old_events=[]),
                     lambda r, c: r.state["requests"][self.inherited_key("hyde")].update(inherited_sha256="0" * 64)]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.assert_resume_rejects(mutation)

    def test_resume_rejects_changed_new_request_and_response_bytes(self):
        for filename in ("request-01.json", "response-01.json"):
            run, _, _ = self.runtime()
            cell = run.cell("Q08", "routed_graphrag", "drift")
            self.inherited_request(run, cell, "primer")
            path = run.directory / filename
            value = b.read(path)
            if filename.startswith("request"):
                value["body"]["input"][0]["content"][0]["text"] += " changed"
            else:
                value["response"]["choices"][0]["message"]["content"] += " changed"
            b.save(path, value)
            with self.assertRaises(b.Halt):
                self.reopen(run)

    def test_same_process_new_cache_also_requires_exact_response_hash(self):
        run, transport, _ = self.runtime()
        cell = run.cell("Q08", "routed_graphrag", "drift")
        self.inherited_request(run, cell, "primer")
        path = run.directory / "response-01.json"
        value = b.read(path)
        value["response"]["choices"][0]["message"]["content"] = "Tampered cached reply"
        b.save(path, value)
        with self.assertRaises(b.Halt):
            self.inherited_request(run, cell, "primer")
        self.assertEqual(len(transport.calls), 1)

    def test_uncertain_reserved_dispatch_without_reply_stops_on_resume(self):
        def crash(_request, _response):
            raise SystemExit("synthetic process loss")
        run, _, _ = self.runtime([crash])
        cell = run.cell("Q08", "routed_graphrag", "drift")
        with self.assertRaises(SystemExit):
            self.inherited_request(run, cell, "primer")
        counts = copy.deepcopy(run.state["counts"])
        resumed = self.reopen(run)
        with self.assertRaisesRegex(b.Halt, "uncertain_dispatch_requires_review"):
            self.inherited_request(resumed, resumed.cell("Q08", "routed_graphrag", "drift"), "primer")
        self.assertEqual(resumed.transport.calls, [])
        self.assertEqual(resumed.state["counts"], counts)
        self.assertIsNone(resumed.state["events"][0]["usage"])
        self.assertEqual(resumed.state["status"], "stopped")

    def test_durable_completed_reply_after_crash_is_reused_without_resend(self):
        def crash(_request, response):
            b.save(response, success(text="Durable before synthetic process loss"))
            raise SystemExit("synthetic process loss")
        run, _, _ = self.runtime([crash])
        cell = run.cell("Q08", "routed_graphrag", "drift")
        with self.assertRaises(SystemExit):
            self.inherited_request(run, cell, "primer")
        counts = copy.deepcopy(run.state["counts"])
        resumed = self.reopen(run)
        answer, _, _ = self.inherited_request(resumed, resumed.cell("Q08", "routed_graphrag", "drift"), "primer")
        self.assertEqual(answer, "Durable before synthetic process loss")
        self.assertEqual(resumed.transport.calls, [])
        self.assertEqual(resumed.state["counts"], counts)
        self.assertTrue(resumed.state["events"][0]["recovered_completed_reply"])
        resumed.verify_ledger()

    def test_resume_rejects_event_stage_cell_request_map_mismatch(self):
        run, _, _ = self.runtime()
        cell = run.cell("Q08", "routed_graphrag", "drift")
        self.inherited_request(run, cell, "primer")
        run.state["events"][0]["stage"] = "local"
        run.persist()
        with self.assertRaises(b.Halt):
            self.reopen(run)

    def test_exclusive_same_directory_lock(self):
        run, _, _ = self.runtime()
        with self.assertRaisesRegex(b.Halt, "runtime_already_active"):
            b.Runtime(run.directory, FakeTransport(), self.enc, self.enc, synthetic=True)


if __name__ == "__main__":
    unittest.main()
