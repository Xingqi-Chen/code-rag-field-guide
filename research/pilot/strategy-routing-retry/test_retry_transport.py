"""Independent offline worker/runner review. All HTTP and credentials are fake.

Run with .cache/graphrag-venv/bin/python -B .../test_retry_transport.py.
The only child spawned by the supervisor test writes a synthetic JSON reply.
"""
from contextlib import contextmanager, ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import urllib.error

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
BLOCKED=[]
def offline_guard(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect'}:
        BLOCKED.append(event);raise RuntimeError('offline_test_network_forbidden')
    if event=='open' and isinstance(args[0],(str,bytes)) and 'credentials.env' in str(args[0]):
        BLOCKED.append('credential_open');raise RuntimeError('offline_test_credential_forbidden')
sys.addaudithook(offline_guard)
import bounded
import transport
import runner
import probe_runtime as probe
SENTINEL='SYNTHETIC_NOT_A_REAL_CREDENTIAL'


def raw_reply(text='visible', *, output=None):
    return json.dumps({'id':'synthetic_response','status':'completed','model':bounded.MODEL,
        'output':output if output is not None else [{'id':'synthetic_message','type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':text}]}],
        'usage':{'input_tokens':3,'output_tokens':5,'total_tokens':8}}).encode()


@contextmanager
def fixture(data=None, *, status=200, ct='application/json', service='generation', fault=None, mutate_state=None, fmt=None):
    with tempfile.TemporaryDirectory() as tmp:
        run=Path(tmp)/'private';run.mkdir(mode=0o700)
        if service=='generation':body=bounded.generation_body(bounded.messages('offline synthetic prompt'),fmt)
        else:body={'model':bounded.EMBED,'input':['offline embedding'],'dimensions':3072,'encoding_format':'float'}
        state={'status':'running','synthetic':False,'supervisor_pid':os.getppid(),'carry':bounded.CARRY,'limits':bounded.LIMITS,
            'events':[{'status':'reserved_before_dispatch','request_body_sha256':hashlib.sha256(json.dumps(body,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()}]}
        if mutate_state:mutate_state(state)
        request=run/'request-01.json';response=run/'response-01.json';bounded.save(run/'summary.json',state);bounded.save(request,{'service':service,'body':body})
        record=NS(run=run,request=request,response=response,calls=[],loads=[],handlers=[],reads=[],body=body)
        payload=raw_reply() if data is None else data
        class Reply:
            headers={'Content-Type':ct,'Set-Cookie':'PRIVATE_COOKIE_CANARY','Authorization':'PRIVATE_HEADER_CANARY'}
            def __init__(self):self.status=status
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):record.reads.append(n);return payload[:n]
        class Opener:
            def open(self,req,timeout):
                record.calls.append({'url':req.full_url,'timeout':timeout,'method':req.method})
                assert req.headers['Authorization']=='Bearer '+SENTINEL
                assert req.full_url==probe.HOSTS[service] and req.full_url.startswith('https://')
                assert json.loads(req.data)==body
                if fault:raise fault
                return Reply()
        def build(*handlers):record.handlers.extend(handlers);return Opener()
        def credential(which):record.loads.append(which);return SENTINEL
        with ExitStack() as stack:
            stack.enter_context(patch.object(transport,'RUN',run))
            stack.enter_context(patch.object(transport,'check_authorization',lambda:None))
            stack.enter_context(patch.object(probe,'load_credential',credential))
            stack.enter_context(patch('urllib.request.build_opener',build))
            stack.enter_context(patch.object(signal,'signal',lambda *args:None))
            stack.enter_context(patch.object(signal,'setitimer',lambda *args:None))
            yield record


class WorkerTests(unittest.TestCase):
    def test_imports_bind_new_runtime_and_transport(self):
        self.assertEqual(Path(bounded.__file__).resolve(),HERE/'bounded.py')
        self.assertEqual(Path(transport.__file__).resolve(),HERE/'transport.py')
        self.assertIs(runner.Runtime,bounded.Runtime);self.assertIs(runner.Transport,transport.Transport)

    def test_raw_is_durable_before_decode_and_only_safe_normalized_reply(self):
        raw=raw_reply(output=[{'id':'reasoning1','type':'reasoning','summary':[{'text':'REASONING_CANARY'}]},
            {'id':'m1','type':'message','role':'assistant','content':[{'type':'output_text','text':'visible'}]}])
        actual=transport.decode_generation;observed=[]
        with fixture(raw) as f:
            def decoder(text,ctype,**kwargs):
                rawpath=f.response.with_suffix('.raw');self.assertEqual(rawpath.read_bytes(),raw)
                self.assertEqual(stat.S_IMODE(rawpath.stat().st_mode),0o600)
                checkpoint=bounded.read(f.response);self.assertEqual(checkpoint['raw_response_sha256'],hashlib.sha256(raw).hexdigest())
                self.assertNotIn('response',checkpoint);observed.append(True)
                return actual(text,ctype,**kwargs)
            with patch.object(transport,'decode_generation',decoder):transport.worker(f.request,f.response)
            result=bounded.read(f.response);self.assertEqual(observed,[True]);self.assertEqual(len(f.calls),1)
            self.assertNotIn('REASONING_CANARY',json.dumps(result));self.assertNotIn('PRIVATE_COOKIE_CANARY',json.dumps(result))
            self.assertNotIn('PRIVATE_HEADER_CANARY',json.dumps(result));self.assertEqual(result['transport_diagnostics']['reasoning_item_count'],1)
            self.assertEqual(result['transport_diagnostics']['provider_usage']['total_tokens'],8)
            self.assertEqual(f.calls[0]['timeout'],120);self.assertEqual(f.calls[0]['method'],'POST')

    def test_decoder_failure_retains_raw_and_diagnostics_without_text(self):
        raw=raw_reply(output=[])
        with fixture(raw) as f:
            transport.worker(f.request,f.response);r=bounded.read(f.response)
            self.assertEqual(r['error_category'],'responses_empty_visible_output');self.assertEqual(r['http_status'],200)
            self.assertEqual(f.response.with_suffix('.raw').read_bytes(),raw);self.assertTrue(r['raw_complete'])
            self.assertEqual(r['transport_diagnostics']['provider_usage']['total_tokens'],8)

    def test_duplicate_worker_returns_original_reply_no_send(self):
        with fixture() as f:
            transport.worker(f.request,f.response);original=f.response.read_bytes();transport.worker(f.request,f.response)
            self.assertEqual(len(f.calls),1);self.assertEqual(f.response.read_bytes(),original)

    def test_existing_claim_marker_without_reply_never_resends(self):
        with fixture() as f:
            bounded.save(f.response.with_suffix('.dispatch.json'),{'dispatch_slot_claimed':True,'dispatch_started':True})
            with self.assertRaises(FileExistsError):transport.worker(f.request,f.response)
            self.assertEqual(f.calls,[]);self.assertEqual(f.loads,[])

    def test_reserved_payload_mismatch_no_credentials_or_send(self):
        with fixture(mutate_state=lambda s:s['events'][0].update(request_body_sha256='0'*64)) as f:
            with self.assertRaises(bounded.Halt) as cm:transport.worker(f.request,f.response)
            self.assertEqual(str(cm.exception),'reserved_payload_changed');self.assertEqual(f.calls,[]);self.assertEqual(f.loads,[])

    def test_invalid_parent_pid_no_credentials_or_send(self):
        with fixture(mutate_state=lambda s:s.update(supervisor_pid=-1)) as f:
            with self.assertRaises(bounded.Halt):transport.worker(f.request,f.response)
            self.assertEqual(f.calls,[]);self.assertEqual(f.loads,[])

    def test_authorization_failure_precedes_credential_loading(self):
        with fixture() as f:
            def reject():raise bounded.Halt('test_authorization_rejected',fatal=True)
            with patch.object(transport,'check_authorization',reject),self.assertRaises(bounded.Halt):transport.worker(f.request,f.response)
            self.assertEqual(f.calls,[]);self.assertEqual(f.loads,[])

    def test_non_running_and_synthetic_ledgers_cannot_dispatch(self):
        for mutation in [lambda s:s.update(status='stopped'),lambda s:s.update(synthetic=True)]:
            with fixture(mutate_state=mutation) as f:
                with self.assertRaises(bounded.Halt):transport.worker(f.request,f.response)
                self.assertEqual(f.calls,[]);self.assertEqual(f.loads,[])

    def test_redirect_handler_rejects_and_https_verifies_certificates(self):
        with fixture() as f:
            transport.worker(f.request,f.response)
            redirect=next(h for h in f.handlers if hasattr(h,'redirect_request'))
            with self.assertRaises(bounded.Halt):redirect.redirect_request(None,None,302,'redirect',{},'https://not-allowed.invalid')
            https=next(h for h in f.handlers if hasattr(h,'_context'))
            self.assertTrue(https._context.check_hostname);self.assertEqual(https._context.verify_mode,ssl.CERT_REQUIRED)

    def test_timeout_classification_and_no_second_same_slot_dispatch(self):
        with fixture(fault=TimeoutError('PRIVATE_EXCEPTION_CANARY')) as f:
            transport.worker(f.request,f.response);r=bounded.read(f.response)
            self.assertEqual(r['error_category'],'transient_connection_error');self.assertNotIn('PRIVATE_EXCEPTION_CANARY',json.dumps(r))
            transport.worker(f.request,f.response);self.assertEqual(len(f.calls),1)

    def test_tls_failure_classification(self):
        with fixture(fault=urllib.error.URLError(ssl.SSLError('PRIVATE_EXCEPTION_CANARY'))) as f:
            transport.worker(f.request,f.response);r=bounded.read(f.response)
            self.assertEqual(r['error_category'],'transport_security_error');self.assertNotIn('PRIVATE_EXCEPTION_CANARY',json.dumps(r))

    def test_http_auth_failure_keeps_fixed_category_not_error_message(self):
        error=urllib.error.HTTPError(probe.HOSTS['generation'],401,'PRIVATE_EXCEPTION_CANARY',{'Content-Type':'application/json'},io.BytesIO(b'{"error":{"message":"invalid api key PRIVATE_CANARY"}}'))
        with fixture(fault=error) as f:
            transport.worker(f.request,f.response);r=bounded.read(f.response)
            self.assertEqual(r['http_status'],401);self.assertEqual(r['error_category'],'authentication_related')
            self.assertNotIn('PRIVATE_CANARY',json.dumps(r));self.assertTrue(f.response.with_suffix('.raw').exists())

    def test_raw_cap_exceeded_stays_partial(self):
        data=b'X'*(2*1024**2+2)
        with fixture(data) as f:
            transport.worker(f.request,f.response);r=bounded.read(f.response)
            self.assertEqual(r['error_category'],'response_byte_cap_exceeded');self.assertFalse(r['raw_complete'])
            self.assertEqual(r['response_bytes'],2*1024**2+1)

    def test_invalid_utf8_retains_raw_and_never_resends(self):
        with fixture(b'\xff\xfe') as f:
            transport.worker(f.request,f.response);r=bounded.read(f.response)
            self.assertEqual(r['error_category'],'worker_exception_redacted');self.assertEqual(f.response.with_suffix('.raw').read_bytes(),b'\xff\xfe')
            transport.worker(f.request,f.response);self.assertEqual(len(f.calls),1)

    def test_exact_official_primer_schema_passes_payload_guard(self):
        from graphrag.query.structured_search.drift_search.primer import PrimerResponse
        schema=PrimerResponse.model_json_schema();schema['additionalProperties']=False
        fmt={'type':'json_schema','name':'PrimerResponse','strict':True,'schema':schema}
        with fixture(raw_reply('{"intermediate_answer":"synthetic","score":1,"follow_up_queries":["q"]}'),fmt=fmt) as f:
            transport.worker(f.request,f.response);self.assertEqual(len(f.calls),1)
            self.assertEqual(f.body['text']['format'],fmt)
            self.assertIn('response',bounded.read(f.response))

    def test_unregistered_schema_fails_before_credentials(self):
        with fixture(fmt={'type':'json_schema','name':'SomethingElse','strict':True,'schema':{}}) as f:
            with self.assertRaises(bounded.Halt) as cm:transport.worker(f.request,f.response)
            self.assertEqual(str(cm.exception),'unregistered_query_schema')
            self.assertEqual(f.calls,[]);self.assertEqual(f.loads,[])

    def test_worker_rejects_wrong_request_directory(self):
        with fixture() as f:
            with self.assertRaises(bounded.Halt):transport.worker(f.run.parent/'request-01.json',f.response)
            self.assertEqual(f.calls,[]);self.assertEqual(f.loads,[])

    def test_embedding_payload_and_timeout(self):
        payload=json.dumps({'model':bounded.EMBED,'data':[{'index':0,'embedding':[0.0]*3072}],'usage':{'prompt_tokens':1,'total_tokens':1}}).encode()
        with fixture(payload,service='embedding') as f:
            transport.worker(f.request,f.response);self.assertEqual(bounded.read(f.response)['response']['model'],bounded.EMBED)
            self.assertEqual(f.calls[0]['timeout'],30);self.assertEqual(f.reads,[4*1024**2+1])

    def test_raw_symlink_refused_without_overwrite(self):
        with fixture() as f:
            target=f.run/'canary';target.write_text('do not overwrite');f.response.with_suffix('.raw').symlink_to(target)
            transport.worker(f.request,f.response);self.assertEqual(target.read_text(),'do not overwrite')
            self.assertEqual(bounded.read(f.response)['error_category'],'worker_exception_redacted')
            transport.worker(f.request,f.response);self.assertEqual(len(f.calls),1)

    def test_checkpoint_reply_after_decode_crash_prevents_repeat(self):
        with fixture() as f:
            def interrupted(*args,**kwargs):raise KeyboardInterrupt
            with patch.object(transport,'decode_generation',interrupted),self.assertRaises(KeyboardInterrupt):transport.worker(f.request,f.response)
            r=bounded.read(f.response);self.assertIn('raw_response_sha256',r);self.assertNotIn('response',r)
            transport.worker(f.request,f.response);self.assertEqual(len(f.calls),1)

    def test_literal_credential_echo_is_removed(self):
        with fixture(raw_reply(SENTINEL)) as f:
            transport.worker(f.request,f.response);self.assertNotIn(SENTINEL,f.response.read_text());self.assertNotIn(SENTINEL.encode(),f.response.with_suffix('.raw').read_bytes())

    def test_json_escaped_credential_echo_cannot_escape_to_visible_reply(self):
        escaped=''.join('\\u%04x'%ord(c) for c in SENTINEL)
        data=raw_reply('ESCAPED_MARKER').replace(b'ESCAPED_MARKER',escaped.encode())
        with fixture(data) as f:
            transport.worker(f.request,f.response);self.assertNotIn(SENTINEL,f.response.read_text())

    def test_sse_escaped_credential_with_initial_comment_is_redacted_privately(self):
        escaped=''.join('\\u%04x'%ord(c) for c in SENTINEL)
        terminal=raw_reply('ESCAPED_MARKER').replace(b'ESCAPED_MARKER',escaped.encode())
        raw=b': keepalive\n\ndata: '+b'{"type":"response.completed","response":'+terminal+b'}\n\n'
        with fixture(raw,ct='text/event-stream') as f:
            transport.worker(f.request,f.response);r=bounded.read(f.response)
            self.assertNotIn(SENTINEL,f.response.read_text())
            persisted=transport.decode_generation(f.response.with_suffix('.raw').read_text(),'text/event-stream')
            self.assertNotIn(SENTINEL,json.dumps(persisted));self.assertTrue(r['raw_redacted'])

    def test_raw_metadata_counts_received_bytes_before_redaction(self):
        data=raw_reply(SENTINEL)
        with fixture(data) as f:
            transport.worker(f.request,f.response);r=bounded.read(f.response)
            self.assertEqual(r['response_bytes'],len(data))
            self.assertTrue(r.get('raw_redacted') is True or r.get('raw_byte_exact') is False)

    def test_redaction_does_not_turn_over_limit_raw_into_complete(self):
        data=(SENTINEL.encode()*((2*1024**2)//len(SENTINEL)+2))
        with fixture(data) as f:
            transport.worker(f.request,f.response);r=bounded.read(f.response)
            self.assertEqual(r['error_category'],'response_byte_cap_exceeded');self.assertFalse(r['raw_complete'])


class RealDataSupervisorTests(unittest.TestCase):
    def test_real_data_then_actual_supervisor_uses_new_worker_path(self):
        previous=probe.supervise;hosts=dict(probe.HOSTS);credentials=probe.load_credential
        legacy=runner.load_legacy();data=legacy.Data()
        self.assertIs(probe.supervise,previous);self.assertEqual(previous.__module__,'probe_runtime')
        self.assertEqual(probe.HOSTS,hosts);self.assertIs(probe.load_credential,credentials)
        self.assertIs(runner.Runtime,bounded.Runtime);self.assertIs(runner.Transport,transport.Transport)
        self.assertIs(legacy.Runtime,bounded.Runtime)
        actual_popen=subprocess.Popen;calls=[]
        with tempfile.TemporaryDirectory() as tmp:
            request=Path(tmp)/'request-01.json';response=Path(tmp)/'response-01.json';request.write_text('{}')
            def child(argv,**kwargs):
                self.assertEqual(argv,[sys.executable,str(HERE/'transport.py'),'worker',str(request),str(response)]);calls.append(argv[2])
                code=('import json,sys;from pathlib import Path;p=Path(sys.argv[1]);'
                    'p.write_text(json.dumps({"http_status":200,"response":{"synthetic":True}}));'
                    'p.with_suffix(".dispatch.json").write_text(json.dumps({"dispatch_started":True}))')
                return actual_popen([sys.executable,'-B','-c',code,str(response)],**kwargs)
            with patch.object(transport,'check_authorization',lambda:None),patch.object(probe.subprocess,'Popen',child):
                r=transport.Transport().dispatch(request,response,5)
            self.assertEqual(r,{'http_status':200,'response':{'synthetic':True},'request_dispatched':True});self.assertEqual(calls,['worker'])
        self.assertFalse(BLOCKED)


if __name__=='__main__':unittest.main(verbosity=2)
