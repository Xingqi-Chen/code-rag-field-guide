"""Network-denied boundary tests; all writes live in temporary directories."""
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bounded import *

def deny(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'}:raise RuntimeError('network forbidden in tests')
    if event=='open' and isinstance(args[0],(str,bytes)) and 'credentials.env' in str(args[0]):raise RuntimeError('credential reads forbidden in tests')
sys.addaudithook(deny)
class Enc:
    def encode(self,text):return list(text)

def reply(text='answer',usage=True):
    return {'http_status':200,'response':{'model':MODEL,'choices':[{'finish_reason':'stop','message':{'content':text}}],
       'usage':{'prompt_tokens':3,'completion_tokens':5,'total_tokens':8} if usage else None}}
class Fake:
    def __init__(self,responses=None):self.responses=responses;self.calls=[];self.active=0;self.max_active=0;self.lock=threading.Lock()
    def check_authorization(self):raise Halt('test_live_launch_forbidden')
    def dispatch(self,request,response,seconds):
        with self.lock:self.active+=1;self.max_active=max(self.max_active,self.active)
        time.sleep(.001)
        body=read(request);self.calls.append(body)
        if self.responses is not None:r=self.responses.pop(0)
        elif body['service']=='embedding':r={'http_status':200,'response':{'model':EMBED,'data':[{'index':0,'embedding':[1.0]*3072}],'usage':{'prompt_tokens':3,'total_tokens':3}}}
        else:r=reply()
        with self.lock:self.active-=1
        return r

class Boundaries(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.runtimes=[]
    def rt(self,transport=None,limits=None,carry=None,create=True):
        r=Runtime(Path(self.tmp.name)/'run',transport or Fake(),Enc(),Enc(),create=create,limits=limits,carry=carry,synthetic=True,wait=lambda _:None)
        self.runtimes.append(r);self.addCleanup(r.close);return r
    def test_live_gate_before_directory_or_dispatch(self):
        d=Path(self.tmp.name)/'live';t=Fake()
        with self.assertRaisesRegex(Halt,'test_live_launch_forbidden'):Runtime(d,t,Enc(),Enc(),create=True)
        self.assertFalse(d.exists());self.assertEqual(t.calls,[])
    def test_fsynced_reservation_and_no_duplicate_success_on_resume(self):
        t=Fake();r=self.rt(t);c=r.cell('Q','bm25','bm25');first=c.generate('question')
        self.assertEqual(r.state['counts']['generation_reservations'],1350)
        r.close();r2=self.rt(t,create=False);c2=r2.cell('Q','bm25','bm25')
        self.assertEqual(c2.generate('question'),first);self.assertEqual(len(t.calls),1)
        self.assertEqual(r2.state['counts']['generation_reservations'],1350)
    def test_complete_invalid_reply_not_replayed(self):
        t=Fake([reply('')]);r=self.rt(t);c=r.cell('Q','bm25','bm25')
        with self.assertRaises(Halt):c.generate('question')
        with self.assertRaises(Halt):c.generate('question')
        self.assertEqual(len(t.calls),1)
    def test_unknown_usage_is_null_and_output_overrun_recorded(self):
        t=Fake([reply('a'*2100,False)]);r=self.rt(t);r.cell('Q','bm25','bm25').generate('question')
        self.assertIsNone(r.state['events'][0]['usage']);self.assertTrue(r.state['events'][0]['requested_output_limit_exceeded'])
    def test_reservation_limit_exact_edge(self):
        limits={**LIMITS,'generation_reservations':1350};t=Fake();r=self.rt(t,limits);r.cell('Q1','bm25','bm25').generate('x')
        with self.assertRaisesRegex(Halt,'generation_reservation_limit'):r.cell('Q2','bm25','bm25').generate('y')
        self.assertEqual(len(t.calls),1)
    def test_request_and_total_input_boundaries(self):
        n=sum(len(m['content']) for m in messages('x'));t=Fake();limits={**LIMITS,'request_input':n,'generation_input_tokens':CARRY['generation_input_tokens']+n}
        r=self.rt(t,limits);r.cell('Q1','bm25','bm25').generate('x')
        with self.assertRaisesRegex(Halt,'request_input_limit'):r.cell('Q2','bm25','bm25').generate('xx')
        with self.assertRaisesRegex(Halt,'generation_total_input_limit'):r.cell('Q3','bm25','bm25').generate('y')
        self.assertEqual(len(t.calls),1)
    def test_retry_consumes_cell_budget_before_next_dispatch(self):
        n=sum(len(m['content']) for m in messages('x'));t=Fake([{'http_status':503}]);r=self.rt(t,{**LIMITS,'cell_input':n})
        with self.assertRaisesRegex(Halt,'cell_input_limit'):r.cell('Q','bm25','bm25').generate('x')
        self.assertEqual(len(t.calls),1);self.assertEqual(r.state['counts']['generation_reservations'],1350)
    def test_three_transient_attempts_share_allowance(self):
        t=Fake([{'http_status':503},{'error_category':'worker_wall_timeout'},{'http_status':429}]);r=self.rt(t)
        with self.assertRaises(Halt):r.cell('Q','bm25','bm25').generate('x')
        self.assertEqual(len(t.calls),3);self.assertEqual(r.state['counts']['generation_reservations'],1352)
    def test_denied_and_invalid_retry_after_do_not_retry(self):
        for value in [{'http_status':503,'error_category':'billing_related'},{'http_status':401},{'http_status':429,'retry_after_invalid':True},{'error_category':'transport_security_error'}]:
            t=Fake([value]);d=Path(self.tmp.name)/str(len(list(Path(self.tmp.name).iterdir())))
            r=Runtime(d,t,Enc(),Enc(),create=True,synthetic=True,wait=lambda _:None)
            try:
                with self.assertRaises(Halt):r.cell('Q','bm25','bm25').generate('x')
                self.assertEqual(len(t.calls),1)
            finally:r.close()
    def test_retry_after_is_respected(self):
        until=datetime.now(timezone.utc)+timedelta(seconds=80)
        event={'status':'failed','http_status':429,'retry_not_before_utc':until.isoformat()}
        self.assertGreater(retry_delay(event,1),79)
    def test_pending_crash_requires_review_and_keeps_reservation(self):
        t=Fake();r=self.rt(t);c=r.cell('Q','bm25','bm25');c.generate('x')
        event=r.state['events'][0];event['status']='reserved_before_dispatch';r.state['requests'][event['key']].pop('completed_response');(r.directory/'response-01.json').unlink();r.persist();r.close()
        r2=self.rt(t,create=False)
        with self.assertRaisesRegex(Halt,'uncertain_dispatch_requires_review'):r2.cell('Q','bm25','bm25').generate('x')
        self.assertEqual(len(t.calls),1)
    def test_completed_worker_reply_recovered_without_dispatch(self):
        t=Fake();r=self.rt(t);c=r.cell('Q','bm25','bm25');c.generate('x')
        event=r.state['events'][0];event['status']='reserved_before_dispatch';r.state['requests'][event['key']].pop('completed_response');r.persist();r.close()
        r2=self.rt(t,create=False);r2.cell('Q','bm25','bm25').generate('x')
        self.assertEqual(len(t.calls),1);self.assertTrue(r2.state['events'][0]['recovered_completed_reply'])
    def test_resume_rejects_reset_counts_and_modified_reply(self):
        t=Fake();r=self.rt(t);r.cell('Q','bm25','bm25').generate('x');r.close()
        state=read(Path(self.tmp.name)/'run/summary.json');state['counts']=CARRY.copy();save(Path(self.tmp.name)/'run/summary.json',state)
        with self.assertRaisesRegex(Halt,'resume_counter_integrity'):self.rt(t,create=False)
        self.assertEqual(len(t.calls),1)
    def test_resume_rejects_changed_completed_response(self):
        t=Fake();r=self.rt(t);r.cell('Q','bm25','bm25').generate('x');r.close()
        save(Path(self.tmp.name)/'run/response-01.json',reply('changed'))
        with self.assertRaisesRegex(Halt,'resume_response_integrity'):self.rt(t,create=False)
        self.assertEqual(len(t.calls),1)
    def test_embedding_item_and_dollar_limits(self):
        t=Fake();cap=Decimal(CARRY['embedding_tokens']+1)*Decimal('.13')/1000000
        r=self.rt(t,{**LIMITS,'embedding_usd':str(cap)})
        r.cell('Q1','hybrid','hybrid').embed(['x'])
        with self.assertRaisesRegex(Halt,'embedding_dollar_limit'):r.cell('Q2','hybrid','hybrid').embed(['y'])
        self.assertEqual(r.state['status'],'stopped')
        self.assertEqual(len(t.calls),1)
    def test_embedding_max_and_account_rejection_stop_correct_scope(self):
        r=self.rt();c=r.cell('Q1','hybrid','hybrid')
        with self.assertRaisesRegex(Halt,'request_input_limit'):c.embed(['z'*8001])
        self.assertEqual(r.state['status'],'running')
        self.assertEqual(len(r.transport.calls),0)
    def test_http_auth_without_known_category_halts_entire_run(self):
        t=Fake([{'http_status':401}]);r=self.rt(t)
        with self.assertRaises(Halt) as caught:r.cell('Q1','bm25','bm25').generate('x')
        self.assertTrue(caught.exception.fatal)
        with self.assertRaises(Halt):r.cell('Q2','bm25','bm25').generate('y')
        self.assertEqual(len(t.calls),1);self.assertEqual(r.state['status'],'stopped')
    def test_generation_and_embedding_share_serial_lock(self):
        t=Fake();r=self.rt(t)
        def call(i):
            c=r.cell(str(i),'hybrid','hybrid');return c.embed([str(i)]) if i%2 else c.generate(str(i))
        with ThreadPoolExecutor(6) as pool:list(pool.map(call,range(6)))
        self.assertEqual(t.max_active,1)
    def test_request_cache_binds_schema_and_model_body(self):
        t=Fake();r=self.rt(t);c=r.cell('Q','routed_graphrag','drift')
        c.generate('same','hyde');c.generate('same','primer',{'type':'json_object'})
        self.assertEqual(len(t.calls),2);self.assertEqual(len(r.state['requests']),2)
    def test_strict_duplicate_and_nonfinite_json_fail(self):
        for text in ['{"x":1,"x":2}','{"x":NaN}','broken']:
            with self.assertRaises(Halt):strict_json(text)
    def test_review_gate_rejects_empty_manifest(self):
        import transport
        from unittest.mock import patch
        original=transport.read
        def reading(path):
            if Path(path).name=='live-readiness.json':return {'status':'independent_review_passed','implementation_sha256':{}}
            return original(path)
        with patch.object(transport,'read',reading),patch.object(Path,'exists',lambda _:True):
            with self.assertRaisesRegex(Halt,'incomplete_review_manifest'):transport.check_authorization()
    def test_live_readiness_gate_currently_stops(self):
        from transport import check_authorization
        if not (Path(__file__).resolve().parents[1]/'live-readiness.json').exists():
            with self.assertRaisesRegex(Halt,'offline_review_not_complete'):check_authorization()

if __name__=='__main__':unittest.main()
