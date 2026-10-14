"""Offline confirmed-EOF recovery: temporary exact ledger copies, fake HTTP/model.

Run with PYTHONHASHSEED=20261012 PYTHONDONTWRITEBYTECODE=1
.cache/graphrag-venv/bin/python <this file> -v.
"""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent))
# Installs network/credential/cache-write guards; no tests or live calls run on import.
import test_manual_recovery as previous
import test_retry_transport as worker_fixture
import bounded as b
import eof_recovery as eof
import probe_runtime as probe
import transport


def generation_success(stage='local'):
    text = (json.dumps({'response': 'Synthetic Local answer.', 'score': 50, 'follow_up_queries': []})
            if stage == 'local' else 'Synthetic reduce answer; not an experimental result.')
    return {'http_status': 200, 'request_dispatched': True,
            'response': {'model': b.MODEL, 'choices': [{'finish_reason': 'stop', 'message': {'content': text}}],
                         'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}}}


def eof_exception(cls=ssl.SSLEOFError):
    error = cls(8, 'synthetic test error')
    error.reason = 'UNEXPECTED_EOF_WHILE_READING'
    return error


class FakeTransport:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.calls = []

    def check_authorization(self):
        pass  # Test double only, with network and credential audit guards active.

    def dispatch(self, request, response, seconds):
        state = b.read(request.parent / 'summary.json')
        event = state['events'][-1]
        assert event['status'] == 'reserved_before_dispatch'
        assert state['eof_recovery']['consumed_by'] == 16
        assert state['events'][15]['reviewed_eof_retry_of'] == 15
        self.calls.append(copy.deepcopy(event))
        action = self.outcomes.pop(0) if self.outcomes else generation_success()
        if callable(action):
            return action(request, response)
        return copy.deepcopy(action)


class WorkerEOFClassification(unittest.TestCase):
    def test_direct_and_urlerror_wrapped_eof_are_connection_failures(self):
        for error in (eof_exception(), urllib.error.URLError(eof_exception())):
            with self.subTest(form=type(error).__name__), worker_fixture.fixture(fault=error) as f:
                transport.worker(f.request, f.response)
                result = b.read(f.response)
                self.assertEqual(result['error_category'], 'transient_connection_error')
                self.assertEqual(result['transport_error_detail']['class'], 'SSLEOFError')
                self.assertEqual(len(f.calls), 1)
                self.assertNotIn('response', result)
                self.assertNotIn('usage', result)
                self.assertEqual(b.retry_delay({**result, 'status': 'failed'}, 1), 5)

    def test_eof_raised_during_body_read_is_classified_without_unknown_usage_invention(self):
        with worker_fixture.fixture() as f:
            original_build = urllib.request.build_opener
            def build(*handlers):
                opener = original_build(*handlers)
                original_open = opener.open
                def opened(*args, **kwargs):
                    reply = original_open(*args, **kwargs)
                    def interrupted_read(_limit):
                        raise eof_exception()
                    reply.read = interrupted_read
                    return reply
                opener.open = opened
                return opener
            with patch('urllib.request.build_opener', build):
                transport.worker(f.request, f.response)
            result = b.read(f.response)
            self.assertEqual(result['error_category'], 'transient_connection_error')
            self.assertNotIn('response', result)
            self.assertNotIn('usage', result)
            self.assertEqual(len(f.calls), 1)

    def test_other_ssl_types_and_same_reason_text_remain_security_failures(self):
        for cls in (ssl.SSLCertVerificationError, ssl.SSLError, ssl.SSLZeroReturnError):
            for wrapped in (False, True):
                error = eof_exception(cls)
                if wrapped:
                    error = urllib.error.URLError(error)
                with self.subTest(cls=cls.__name__, wrapped=wrapped), worker_fixture.fixture(fault=error) as f:
                    transport.worker(f.request, f.response)
                    result = b.read(f.response)
                    self.assertEqual(result['error_category'], 'transport_security_error')
                    self.assertIsNone(b.retry_delay({**result, 'status': 'failed'}, 1))
                    self.assertTrue(b.run_fatal(result['error_category']))

    def test_workers_construct_new_verified_contexts_and_do_not_retry_internally(self):
        contexts = []
        for _ in range(2):
            with worker_fixture.fixture(fault=eof_exception()) as f:
                transport.worker(f.request, f.response)
                https = next(h for h in f.handlers if isinstance(h, urllib.request.HTTPSHandler))
                contexts.append(https._context)
                self.assertTrue(https._context.check_hostname)
                self.assertEqual(https._context.verify_mode, ssl.CERT_REQUIRED)
                self.assertEqual(len(f.calls), 1)
        self.assertIsNot(contexts[0], contexts[1])


class EOFRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = ROOT / '.cache/pilot/strategy-routing-retry-20261014'
        cls.raw = (cls.real / 'summary.json').read_bytes()
        if hashlib.sha256(cls.raw).hexdigest() != eof.STOP_SHA:
            cls.raw = (cls.real / 'stopped-summary-event15.json').read_bytes()
        assert hashlib.sha256(cls.raw).hexdigest() == eof.STOP_SHA
        cls.before = json.loads(cls.raw)
        cls.key = cls.before['events'][14]['key']
        cls.enc, cls.eenc = probe.tokenizers()
        cls.protected = {p: b.file_sha(p) for p in cls.real.glob('*.json')}

    @classmethod
    def tearDownClass(cls):
        for path, sha in cls.protected.items():
            if b.file_sha(path) != sha:
                raise AssertionError('Original retry-run file changed during offline EOF tests')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='eof-recovery-test-')
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.review_dir = self.folder / 'review'
        self.review_dir.mkdir()
        files = {}
        for name in ('eof_recovery.py', 'eof-stop.json', 'bounded.py', 'runner.py', 'transport.py',
                     'manual_recovery.py', 'authorization.json', 'inherited-manifest.json', 'responses_decoder.py'):
            data = (HERE / name).read_bytes()
            (self.review_dir / name).write_bytes(data)
            files[name] = hashlib.sha256(data).hexdigest()
        b.save(self.review_dir / 'eof-review.json', {'status': 'independent_review_passed',
               'stopped_summary_sha256': eof.STOP_SHA, 'implementation_sha256': files})
        self.addCleanup(patch.stopall)
        patch.object(eof, 'HERE', self.review_dir).start()
        self.serial = 0

    def fixture(self, outcomes=()):
        self.serial += 1
        directory = self.folder / str(self.serial)
        directory.mkdir()
        for seq in range(1, 16):
            for stem in ('request', 'response'):
                name = f'{stem}-{seq:02}.json'
                (directory / name).write_bytes((self.real / name).read_bytes())
        (directory / 'summary.json').write_bytes(self.raw)
        (directory / 'stopped-summary-event15.json').write_bytes(self.raw)
        (directory / 'stopped-summary-event12.json').write_bytes((self.real / 'stopped-summary-event12.json').read_bytes())
        fake = FakeTransport(outcomes)
        waits = []
        runtime = b.Runtime(directory, fake, self.enc, self.eenc, adopt_controller=False, wait=waits.append)
        self.addCleanup(runtime.close)
        return runtime, fake, waits

    def resume(self, runtime):
        runtime.close()
        new = b.Runtime(runtime.directory, FakeTransport(), self.enc, self.eenc, adopt_controller=False, wait=lambda _: None)
        self.addCleanup(new.close)
        return new

    def assert_history(self, runtime):
        self.assertEqual(runtime.state['events'][:15], self.before['events'])
        self.assertEqual(b.canonical(runtime.state['events'][14]), b.canonical(self.before['events'][14]))
        self.assertEqual(runtime.state['manual_recovery'], self.before['manual_recovery'])
        self.assertEqual(runtime.state['cells']['Q08:routed_graphrag'], self.before['cells']['Q08:routed_graphrag'])
        self.assertEqual(runtime.state['carry'], self.before['carry'])
        self.assertEqual(runtime.state['limits'], self.before['limits'])
        self.assertIsNone(runtime.state['events'][14]['usage'])
        self.assertEqual((runtime.directory / 'stopped-summary-event15.json').read_bytes(), self.raw)
        self.assertEqual((runtime.directory / 'response-15.json').read_bytes(), (self.real / 'response-15.json').read_bytes())

    def test_authorization_preserves_events_counts_previous_manual_exception(self):
        runtime, fake, _ = self.fixture()
        eof.authorize(runtime)
        self.assertEqual(runtime.state['counts'], self.before['counts'])
        self.assertEqual(runtime.state['status'], 'running')
        self.assertEqual(runtime.state['cells'][eof.CELL]['status'], 'running')
        self.assert_history(runtime)
        self.assertEqual(fake.calls, [])
        self.resume(runtime).verify_ledger()

    def test_exact_snapshot_response_and_review_are_required(self):
        for target in ('summary.json', 'stopped-summary-event15.json', 'response-15.json', 'review'):
            runtime, fake, _ = self.fixture()
            if target == 'response-15.json':
                eof.authorize(runtime)
                p = runtime.directory / target
                p.write_bytes(p.read_bytes() + b' ')
                with self.assertRaises(b.Halt):
                    eof.prefetch(runtime)
            else:
                p = self.review_dir / 'eof-review.json' if target == 'review' else runtime.directory / target
                if target == 'review':
                    review = b.read(p)
                    review['status'] = 'pending'
                    b.save(p, review)
                else:
                    p.write_bytes(p.read_bytes() + b' ')
                with self.assertRaises(b.Halt):
                    eof.authorize(runtime)
            self.assertEqual(fake.calls, [])

    def test_authorization_is_once_only_and_prefetch_body_is_exact(self):
        runtime, fake, waits = self.fixture()
        eof.authorize(runtime)
        with self.assertRaises(b.Halt):
            eof.authorize(runtime)
        eof.prefetch(runtime)
        self.assertEqual((runtime.directory / 'request-16.json').read_bytes(), (runtime.directory / 'request-15.json').read_bytes())
        self.assertEqual(fake.calls[0]['key'], self.key)
        self.assertEqual(fake.calls[0]['reviewed_eof_retry_of'], 15)
        self.assertEqual(waits, [5])
        self.assertEqual(runtime.state['counts']['generation_reservations'], 1507)
        self.assertEqual(runtime.state['counts']['generation_input_tokens'], 3122264)
        eof.prefetch(runtime)
        self.assertEqual(len(fake.calls), 1)
        self.assert_history(runtime)
        self.resume(runtime).verify_ledger()

    def test_pending_other_request_rejected_without_mutation_or_orphan(self):
        runtime, fake, _ = self.fixture()
        eof.authorize(runtime)
        before = copy.deepcopy(runtime.state)
        body = {'model': b.EMBED, 'input': ['unrelated new Local action'], 'dimensions': 3072, 'encoding_format': 'float'}
        with self.assertRaises(b.Halt):
            runtime.request(eof.CELL, 'embedding', body, 'query_embedding')
        self.assertEqual(runtime.state, before)
        self.assertEqual(fake.calls, [])
        self.resume(runtime).verify_ledger()

    def test_exact_event_fields_cannot_be_reinterpreted_for_other_failures(self):
        for field, value in [('key', 'changed'), ('cell', 'Q08:routed_graphrag'), ('status', 'validated'),
                             ('error_category', 'permission_related'), ('service', 'embedding'),
                             ('request_body_sha256', '0' * 64)]:
            runtime, fake, _ = self.fixture()
            eof.authorize(runtime)
            changed = copy.deepcopy(runtime.state['events'][14])
            changed[field] = value
            with self.assertRaises(b.Halt):
                eof.eligible(runtime, changed, runtime.state['requests'][self.key])
            self.assertEqual(fake.calls, [])

    def test_shared_eof_timeout_http_attempt_limit_is_three_including_original(self):
        for outcomes in ([previous.failed('transient_connection_error'), previous.failed('model_related', 503)],
                         [previous.failed('worker_wall_timeout'), generation_success()]):
            runtime, fake, waits = self.fixture(outcomes)
            eof.authorize(runtime)
            if 'response' in outcomes[-1]:
                eof.prefetch(runtime)
            else:
                with self.assertRaises(b.Halt) as error:
                    eof.prefetch(runtime)
                self.assertFalse(error.exception.fatal)
                self.assertEqual(runtime.state['status'], 'running')
                self.assertEqual(runtime.state['cells'][eof.CELL]['status'], 'failed')
            self.assertEqual(len(fake.calls), 2)
            self.assertEqual(waits, [5, 15])
            self.assertEqual(runtime.state['requests'][self.key]['events'], [15, 16, 17])
            self.assertEqual(runtime.state['counts']['generation_reservations'], 1508)
            self.assertEqual(runtime.state['counts']['generation_input_tokens'], 3125512)
            self.assertEqual(runtime.state['counts']['embedding_attempts'], 154)
            self.assertEqual(runtime.state['eof_recovery']['consumed_by'], 16)
            eof.prefetch(runtime)
            self.assertEqual(len(fake.calls), 2)
            self.assert_history(runtime)
            self.resume(runtime).verify_ledger()

    def test_certificate_and_authentication_still_stop_whole_run(self):
        for failure in (previous.failed('transport_security_error'), previous.failed('authentication_related', 401)):
            runtime, fake, waits = self.fixture([failure])
            eof.authorize(runtime)
            with self.assertRaises(b.Halt) as error:
                eof.prefetch(runtime)
            self.assertTrue(error.exception.fatal)
            self.assertEqual(runtime.state['status'], 'stopped')
            self.assertEqual(len(fake.calls), 1)
            self.assertEqual(waits, [5])
            self.assert_history(runtime)

    def test_unknown_crash_after_consumption_does_not_replay(self):
        def crash(_request, _response):
            raise SystemExit('synthetic process loss')
        runtime, fake, _ = self.fixture([crash])
        eof.authorize(runtime)
        with self.assertRaises(SystemExit):
            eof.prefetch(runtime)
        self.assertEqual(runtime.state['eof_recovery']['consumed_by'], 16)
        resumed = self.resume(runtime)
        body = resumed.state['requests'][self.key]['body']
        with self.assertRaisesRegex(b.Halt, 'uncertain_dispatch_requires_review'):
            resumed.request(eof.CELL, 'generation', body, 'local')
        self.assertEqual(resumed.transport.calls, [])
        self.assertEqual(resumed.state['counts']['generation_reservations'], 1507)
        self.assert_history(resumed)

    def test_resume_rejects_modified_history_or_consumption(self):
        for target in ('event15', 'consumed', 'snapshot'):
            runtime, _, _ = self.fixture()
            eof.authorize(runtime)
            eof.prefetch(runtime)
            if target == 'event15':
                runtime.state['events'][14]['error_category'] = 'transient_connection_error'
            elif target == 'consumed':
                runtime.state['eof_recovery']['consumed_by'] = 17
            else:
                p = runtime.directory / 'stopped-summary-event15.json'
                p.write_bytes(p.read_bytes() + b' ')
            runtime.persist()
            with self.assertRaises(b.Halt):
                self.resume(runtime)

    def test_real_q10_official_cache_chain_after_exact_local_prefetch(self):
        from runner import load_legacy
        legacy = load_legacy()
        queries = legacy.verify_protocol()
        data = legacy.Data()
        q = next(q for q in queries if q['id'] == 'Q10')
        runtime, _, waits = self.fixture()
        eof.authorize(runtime)

        class OfficialFake(FakeTransport):
            def dispatch(self, request, response, seconds):
                state = b.read(request.parent / 'summary.json')
                event = state['events'][-1]
                assert state['eof_recovery']['consumed_by'] == 16
                assert event['cell'] == eof.CELL
                if not self.calls:
                    assert event['sequence'] == 16 and event['key'] == self_key
                    assert b.read(request) == b.read(runtime.directory / 'request-15.json')
                self.calls.append(copy.deepcopy(event))
                if event['service'] == 'embedding':
                    value = previous.embed_success()
                    value['response']['data'][0]['embedding'] = [1.0] * 3072
                    return value
                return generation_success(event['stage'])

        self_key = self.key
        fake = OfficialFake()
        runtime.transport = fake
        eof.prefetch(runtime)
        prior_uses = len(runtime.state['cells'][eof.CELL]['uses'])
        cell = runtime.cell('Q10', 'routed_graphrag', 'drift')
        asyncio.run(legacy.execute_cell(data, cell, q))
        self.assertEqual(cell.data['status'], 'complete', cell.data.get('failure'))
        self.assertEqual(len(fake.calls), 7)
        self.assertEqual(sum(e['service'] == 'embedding' for e in fake.calls), 2)
        self.assertEqual(sum(e['stage'] == 'local' for e in fake.calls), 4)
        self.assertEqual(sum(e['stage'] == 'reduce' for e in fake.calls), 1)
        uses = cell.data['uses'][prior_uses:]
        self.assertEqual([(u['stage'], u['cache']) for u in uses[:3]],
                         [('hyde', True), ('query_embedding', True), ('primer', True)])
        cached_origins = {u['origin_event'] for u in uses if u['cache']}
        self.assertTrue({62, 63, 11, 13, 14, 16} <= cached_origins)
        self.assertEqual(waits, [5])
        self.assertEqual(runtime.state['counts']['generation_reservations'], 1511)
        self.assertEqual(runtime.state['counts']['embedding_attempts'], 156)
        self.assert_history(runtime)
        runtime.verify_ledger()
        self.resume(runtime).verify_ledger()


if __name__ == '__main__':
    unittest.main()
