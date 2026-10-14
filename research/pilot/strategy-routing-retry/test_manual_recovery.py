"""Offline event12 manual-recovery tests; only temporary ledger copies mutate.

Uses cached tokenizers and a fake transport, never the production worker.
Run with PYTHONDONTWRITEBYTECODE=1 .cache/graphrag-venv/bin/python <this file> -v.
"""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent))


def offline_guard(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "http.client.connect", "urllib.Request"}:
        raise RuntimeError("manual recovery tests forbid network")
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if ("credentials" in path.name.lower() and path.suffix not in {".py", ".pyc"}) or path.suffix == ".env":
            raise RuntimeError("manual recovery tests forbid credentials")
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(x in mode for x in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing and path.is_relative_to(ROOT / ".cache"):
            raise RuntimeError("manual recovery tests forbid original cache writes")


sys.addaudithook(offline_guard)
import bounded as b
import manual_recovery as m
import probe_runtime as probe


def embed_success():
    return {"http_status": 200, "request_dispatched": True,
            "response": {"model": b.EMBED, "data": [{"index": 0, "embedding": [0.0] * 3072}],
                         "usage": {"prompt_tokens": 13, "total_tokens": 13}}}


def failed(category, status=None):
    return {"http_status": status, "request_dispatched": True, "error_category": category}


class FakeTransport:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.calls = []

    def check_authorization(self):
        # Solely for exact copies of the nonsynthetic stopped ledger. No worker
        # is imported or dispatched; the test audit hook denies real network.
        pass

    def dispatch(self, request, response, seconds):
        state = b.read(request.parent / "summary.json")
        event = state["events"][-1]
        assert event["status"] == "reserved_before_dispatch"
        assert state["manual_recovery"]["consumed_by"] == 13
        assert state["events"][12]["manual_retry_of"] == 12
        assert event["key"] == m.KEY
        self.calls.append((request.name, seconds, copy.deepcopy(state["counts"])))
        action = self.outcomes.pop(0) if self.outcomes else embed_success()
        if callable(action):
            return action(request, response)
        return copy.deepcopy(action)


class ManualRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = ROOT / ".cache/pilot/strategy-routing-retry-20261014"
        cls.raw_summary = (cls.real / "summary.json").read_bytes()
        if hashlib.sha256(cls.raw_summary).hexdigest() != m.STOP_SHA:
            # Allow replay after the authorized run advances, using its immutable
            # stopped snapshot. Tests never modify the current actual run.
            cls.raw_summary = (cls.real / "stopped-summary-event12.json").read_bytes()
        assert hashlib.sha256(cls.raw_summary).hexdigest() == m.STOP_SHA
        cls.before = json.loads(cls.raw_summary)
        cls.enc, cls.eenc = probe.tokenizers()
        cls.protected = {p: b.file_sha(p) for p in cls.real.glob("*.json")}
        cls.original_event12 = b.canonical(cls.before["events"][11])
        cls.original_q08 = copy.deepcopy(cls.before["cells"]["Q08:routed_graphrag"])

    @classmethod
    def tearDownClass(cls):
        for path, sha in cls.protected.items():
            if b.file_sha(path) != sha:
                raise AssertionError("original retry-run file changed during offline tests")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="manual-tls-recovery-test-")
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.review_dir = self.folder / "review"
        self.review_dir.mkdir()
        files = {}
        for name in ("manual_recovery.py", "bounded.py", "transport.py", "runner.py", "authorization.json",
                     "inherited-manifest.json", "responses_decoder.py", "transport-stop.json"):
            data = (HERE / name).read_bytes()
            (self.review_dir / name).write_bytes(data)
            files[name] = hashlib.sha256(data).hexdigest()
        b.save(self.review_dir / "manual-resume-review.json", {
            "status": "independent_review_passed", "stopped_summary_sha256": m.STOP_SHA,
            "implementation_sha256": files})
        self.addCleanup(patch.stopall)
        patch.object(m, "HERE", self.review_dir).start()
        self.serial = 0

    def fixture(self, outcomes=()):
        self.serial += 1
        directory = self.folder / str(self.serial)
        directory.mkdir()
        for seq in range(1, 13):
            for stem in ("request", "response"):
                name = f"{stem}-{seq:02}.json"
                (directory / name).write_bytes((self.real / name).read_bytes())
        (directory / "summary.json").write_bytes(self.raw_summary)
        (directory / "stopped-summary-event12.json").write_bytes(self.raw_summary)
        transport = FakeTransport(outcomes)
        waits = []
        runtime = b.Runtime(directory, transport, self.enc, self.eenc, adopt_controller=False, wait=waits.append)
        self.addCleanup(runtime.close)
        return runtime, transport, waits

    def replay(self, runtime):
        record = runtime.state["requests"][m.KEY]
        return runtime.request(m.CELL, "embedding", copy.deepcopy(record["body"]), "query_embedding")

    def resume(self, runtime):
        runtime.close()
        resumed = b.Runtime(runtime.directory, FakeTransport(), self.enc, self.eenc, adopt_controller=False, wait=lambda _: None)
        self.addCleanup(resumed.close)
        return resumed

    def assert_history(self, runtime):
        self.assertEqual(runtime.state["events"][:12], self.before["events"])
        self.assertEqual(b.canonical(runtime.state["events"][11]), self.original_event12)
        self.assertEqual(runtime.state["cells"]["Q08:routed_graphrag"], self.original_q08)
        self.assertEqual(runtime.state["carry"], self.before["carry"])
        self.assertEqual(runtime.state["limits"], self.before["limits"])
        self.assertIsNone(runtime.state["events"][11]["usage"])
        self.assertEqual((runtime.directory / "stopped-summary-event12.json").read_bytes(), self.raw_summary)

    def test_authorize_only_exact_snapshot_without_count_or_event_mutation(self):
        runtime, transport, _ = self.fixture()
        m.authorize(runtime)
        self.assert_history(runtime)
        self.assertEqual(runtime.state["counts"], self.before["counts"])
        self.assertEqual(runtime.state["status"], "running")
        self.assertEqual(runtime.state["cells"][m.CELL]["status"], "running")
        self.assertEqual(runtime.state["cells"][m.CELL]["historical_stop"],
                         {"failure": "transport_security_error", "fatal": True})
        self.assertEqual(transport.calls, [])
        self.resume(runtime).verify_ledger()

    def test_changed_snapshot_summary_or_state_cannot_be_authorized(self):
        for target in ("summary.json", "stopped-summary-event12.json", "memory"):
            runtime, transport, _ = self.fixture()
            if target == "memory":
                runtime.state["counts"]["embedding_attempts"] -= 1
            else:
                path = runtime.directory / target
                path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaises(b.Halt):
                m.authorize(runtime)
            self.assertEqual(transport.calls, [])

    def test_review_hash_gate_is_required(self):
        runtime, transport, _ = self.fixture()
        (self.review_dir / "bounded.py").write_text("changed")
        with self.assertRaisesRegex(b.Halt, "manual_resume_review_changed"):
            m.authorize(runtime)
        self.assertEqual(transport.calls, [])

    def test_authorization_cannot_be_applied_twice(self):
        runtime, transport, _ = self.fixture()
        m.authorize(runtime)
        counts = copy.deepcopy(runtime.state["counts"])
        with self.assertRaises(b.Halt):
            m.authorize(runtime)
        self.assertEqual(runtime.state["counts"], counts)
        self.assertEqual(transport.calls, [])

    def test_manual_slot_rejects_wrong_key_body_service_status_or_attempts(self):
        for field, changed in [("key", "wrong"), ("request_body_sha256", "0" * 64),
                               ("service", "generation"), ("stage", "primer"),
                               ("cell", "Q08:routed_graphrag"), ("status", "validated"),
                               ("error_category", "permission_related")]:
            runtime, transport, _ = self.fixture()
            m.authorize(runtime)
            event = copy.deepcopy(runtime.state["events"][11])
            event[field] = changed
            with self.assertRaisesRegex(b.Halt, "manual_resume_slot_invalid"):
                m.eligible(runtime, event, runtime.state["requests"][m.KEY])
            self.assertEqual(transport.calls, [])
        runtime, _, _ = self.fixture()
        m.authorize(runtime)
        record = copy.deepcopy(runtime.state["requests"][m.KEY])
        record["events"] = [12, 13]
        with self.assertRaisesRegex(b.Halt, "manual_resume_slot_invalid"):
            m.eligible(runtime, runtime.state["events"][11], record)

    def test_success_reserves_only_second_attempt_and_caches_after_resume(self):
        runtime, transport, waits = self.fixture()
        m.authorize(runtime)
        value = self.replay(runtime)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0][:2], ("request-13.json", 30))
        self.assertEqual(waits, [])
        self.assertEqual(runtime.state["requests"][m.KEY]["events"], [12, 13])
        expected = {**self.before["counts"], "embedding_tokens": 666643, "embedding_attempts": 153}
        self.assertEqual(runtime.state["counts"], expected)
        self.assertEqual(runtime.state["manual_recovery"]["consumed_by"], 13)
        self.assert_history(runtime)
        resumed = self.resume(runtime)
        self.assertEqual(self.replay(resumed), value)
        self.assertEqual(resumed.transport.calls, [])
        self.assertEqual(resumed.state["counts"], expected)
        self.assert_history(resumed)

    def test_second_tls_failure_stops_without_third_attempt(self):
        runtime, transport, waits = self.fixture([failed("transport_security_error")])
        m.authorize(runtime)
        with self.assertRaisesRegex(b.Halt, "transport_security_error"):
            self.replay(runtime)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(waits, [])
        self.assertEqual(runtime.state["status"], "stopped")
        self.assertEqual(runtime.state["requests"][m.KEY]["events"], [12, 13])
        self.assert_history(runtime)
        resumed = self.resume(runtime)
        with self.assertRaisesRegex(b.Halt, "transport_security_error"):
            self.replay(resumed)
        self.assertEqual(resumed.transport.calls, [])

    def test_transient_second_attempt_may_use_only_one_final_slot(self):
        for final in (embed_success(), failed("model_related", 503)):
            runtime, transport, waits = self.fixture([failed("worker_wall_timeout"), final])
            m.authorize(runtime)
            if "response" in final:
                self.replay(runtime)
            else:
                with self.assertRaises(b.Halt):
                    self.replay(runtime)
            self.assertEqual(len(transport.calls), 2)
            self.assertEqual(waits, [15])
            self.assertEqual(runtime.state["requests"][m.KEY]["events"], [12, 13, 14])
            self.assertEqual(runtime.state["counts"]["embedding_attempts"], 154)
            self.assertEqual(runtime.state["counts"]["embedding_tokens"], 666656)
            self.assertEqual(runtime.state["manual_recovery"]["consumed_by"], 13)
            self.assert_history(runtime)
            self.resume(runtime).verify_ledger()

    def test_permission_failure_remains_fatal_after_manual_slot(self):
        runtime, transport, waits = self.fixture([failed("permission_related", 403)])
        m.authorize(runtime)
        with self.assertRaises(b.Halt):
            self.replay(runtime)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(waits, [])
        self.assertEqual(runtime.state["status"], "stopped")
        self.assert_history(runtime)

    def test_pending_manual_slot_rejects_any_other_new_reservation(self):
        runtime, transport, _ = self.fixture()
        m.authorize(runtime)
        body = {'model': b.EMBED, 'input': ['A different pending Local action'],
                'dimensions': 3072, 'encoding_format': 'float'}
        with self.assertRaises(b.Halt):
            runtime.request(m.CELL, 'embedding', body, 'query_embedding')
        self.assertEqual(transport.calls, [])
        self.assertEqual(len(runtime.state['events']), 12)
        self.assertEqual(runtime.state['counts'], self.before['counts'])
        self.assertIsNone(runtime.state['manual_recovery']['consumed_by'])
        self.resume(runtime).verify_ledger()

    def test_consumption_persists_before_dispatch_and_unknown_crash_cannot_replay(self):
        def crash(_request, _response):
            raise SystemExit("synthetic host loss")
        runtime, transport, _ = self.fixture([crash])
        m.authorize(runtime)
        with self.assertRaises(SystemExit):
            self.replay(runtime)
        self.assertEqual(runtime.state["manual_recovery"]["consumed_by"], 13)
        self.assertEqual(runtime.state["events"][12]["status"], "reserved_before_dispatch")
        self.assertEqual(len(transport.calls), 1)
        resumed = self.resume(runtime)
        with self.assertRaisesRegex(b.Halt, "uncertain_dispatch_requires_review"):
            self.replay(resumed)
        self.assertEqual(resumed.transport.calls, [])
        self.assertEqual(resumed.state["counts"]["embedding_attempts"], 153)
        self.assert_history(resumed)

    def test_resume_rejects_old_event_or_manual_consumption_mutation(self):
        for target in ("old_event", "consumption", "snapshot"):
            runtime, _, _ = self.fixture()
            m.authorize(runtime)
            self.replay(runtime)
            if target == "old_event":
                runtime.state["events"][11]["request_dispatched"] = False
            elif target == "consumption":
                runtime.state["manual_recovery"]["consumed_by"] = None
            else:
                path = runtime.directory / "stopped-summary-event12.json"
                path.write_bytes(path.read_bytes() + b" ")
            runtime.persist()
            with self.assertRaises(b.Halt):
                self.resume(runtime)

    def test_completed_q08_is_preserved_and_controller_skips_it(self):
        runtime, transport, _ = self.fixture()
        m.authorize(runtime)
        self.replay(runtime)
        cell = runtime.cell("Q08", "routed_graphrag", "drift")
        self.assertEqual(cell.data["status"], "complete")
        self.assertEqual(cell.data, self.original_q08)
        self.assertEqual([c for c in runtime.state["cells"] if runtime.state["cells"][c]["status"] not in {"complete", "failed"}], [m.CELL])
        self.assertEqual(len(transport.calls), 1)

    def test_real_data_and_official_q10_replay_reach_exact_event12_key(self):
        from runner import load_legacy
        legacy = load_legacy()
        queries = legacy.verify_protocol()
        data = legacy.Data()
        q = next(q for q in queries if q['id'] == 'Q10')
        runtime, _, _ = self.fixture()
        m.authorize(runtime)
        prior_uses = len(runtime.state['cells'][m.CELL]['uses'])

        class OfficialFake(FakeTransport):
            def dispatch(self, request, response, seconds):
                state = b.read(request.parent / 'summary.json')
                event = state['events'][-1]
                task = b.read(request)
                assert event['status'] == 'reserved_before_dispatch'
                assert state['manual_recovery']['consumed_by'] == 13
                assert event['cell'] == m.CELL
                if not self.calls:
                    assert event['sequence'] == 13 and event['key'] == m.KEY
                    assert event['request_body_sha256'] == m.BODY_SHA
                    assert task == b.read(runtime.directory / 'request-12.json')
                self.calls.append(copy.deepcopy(event))
                if task['service'] == 'embedding':
                    value = embed_success()
                    value['response']['data'][0]['embedding'] = [1.0] * 3072
                    return value
                assert event['stage'] in {'local', 'reduce'}
                text = (json.dumps({'response': 'Synthetic Local answer.', 'score': 50, 'follow_up_queries': []})
                        if event['stage'] == 'local' else 'Synthetic reduce answer. Not an experimental result.')
                return {'http_status': 200, 'request_dispatched': True,
                        'response': {'model': b.MODEL, 'choices': [{'finish_reason': 'stop', 'message': {'content': text}}],
                                     'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}}}

        fake = OfficialFake()
        runtime.transport = fake
        m.prefetch(runtime)
        prior_uses = len(runtime.state['cells'][m.CELL]['uses'])
        cell = runtime.cell('Q10', 'routed_graphrag', 'drift')
        errors = []
        original_drift = legacy.drift
        async def diagnostic_drift(*args, **kwargs):
            try:
                return await original_drift(*args, **kwargs)
            except Exception as error:
                errors.append((type(error).__name__, str(error)))
                raise
        with patch.object(legacy, 'drift', diagnostic_drift):
            asyncio.run(legacy.execute_cell(data, cell, q))
        self.assertEqual(cell.data['status'], 'complete', (cell.data.get('failure'), errors))
        self.assertEqual(len(fake.calls), 9)
        self.assertEqual([e['stage'] for e in fake.calls].count('local'), 4)
        self.assertEqual([e['stage'] for e in fake.calls].count('reduce'), 1)
        self.assertEqual([e['service'] for e in fake.calls].count('embedding'), 4)
        new_uses = cell.data['uses'][prior_uses:]
        self.assertEqual([(u['stage'], u['cache']) for u in new_uses[:3]],
                         [('hyde', True), ('query_embedding', True), ('primer', True)])
        self.assertEqual([u['origin_event'] for u in new_uses[:3]], [62, 63, 11])
        self.assertTrue(any(u['key'] == m.KEY and u['cache'] and u['origin_event'] == 13 for u in new_uses))
        self.assertEqual(runtime.state['counts']['generation_reservations'], 1510)
        self.assertEqual(runtime.state['counts']['embedding_attempts'], 156)
        self.assert_history(runtime)
        runtime.verify_ledger()
        self.resume(runtime).verify_ledger()


if __name__ == "__main__":
    unittest.main()
