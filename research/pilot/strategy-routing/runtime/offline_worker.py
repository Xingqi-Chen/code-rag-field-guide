"""Exercise the real one-shot worker with an in-memory HTTP opener only."""
import json
import os
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch

from bounded import CARRY,LIMITS,MODEL,EMBED,messages,generation_body,save,read
import transport


def check_worker():
    import probe_runtime as probe
    from graphrag.query.structured_search.drift_search.primer import PrimerResponse
    schema=PrimerResponse.model_json_schema();schema['additionalProperties']=False
    primer_fmt={'type':'json_schema','name':'PrimerResponse','strict':True,'schema':schema}
    bodies=[('generation',generation_body(messages('test primer'),primer_fmt)),
            ('generation',generation_body(messages('test Local JSON'),{'type':'json_object'})),
            ('embedding',{'model':EMBED,'input':['test embedding'],'dimensions':3072,'encoding_format':'float'})]
    calls=[]
    class Response:
        status=200
        headers={'Content-Type':'application/json'}
        def __init__(self,payload):self.payload=payload
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n):return json.dumps(self.payload).encode()
    class Opener:
        def open(self,request,timeout):
            body=json.loads(request.data)
            calls.append({'body':body,'timeout':timeout,'authorization_is_synthetic':request.headers.get('Authorization')=='Bearer SYNTHETIC_NOT_A_CREDENTIAL'})
            if body['model']==EMBED:payload={'model':EMBED,'data':[{'index':0,'embedding':[1.0]*3072}],'usage':{'prompt_tokens':3,'total_tokens':3}}
            else:payload={'id':'synthetic-response','status':'completed','model':MODEL,'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'synthetic visible response'}]}],'usage':{'input_tokens':3,'output_tokens':5,'total_tokens':8}}
            return Response(payload)
    old_run,old_limits,old_validate=probe.RUN,probe.LIMITS,probe.validate_payload
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'.cache/pilot/strategy-routing-20261014';run.mkdir(parents=True)
            for service,body in bodies:
                seq=len(calls)+1
                state={'status':'running','supervisor_pid':os.getppid(),'synthetic':False,'limits':LIMITS,'carry':CARRY,
                    'events':[{}]*(seq-1)+[{'status':'reserved_before_dispatch','request_body_sha256':probe.digest(probe.canonical(body).encode())}]}
                save(run/'summary.json',state)
                request,response=run/f'request-{seq:02}.json',run/f'response-{seq:02}.json'
                save(request,{'service':service,'body':body})
                with patch.object(transport,'ROOT',root),patch.object(transport,'check_authorization',lambda:None),\
                     patch.object(probe,'load_credential',lambda _: 'SYNTHETIC_NOT_A_CREDENTIAL'),\
                     patch('urllib.request.build_opener',lambda *args:Opener()):
                    transport.worker(request,response)
                assert read(response)['http_status']==200
                assert read(response)['response']['model']==body['model']
                assert len(calls)==seq
                original_reply=response.read_bytes()
                # One reservation cannot be dispatched twice or overwrite its reply.
                with patch.object(transport,'ROOT',root),patch.object(transport,'check_authorization',lambda:None),\
                     patch.object(probe,'load_credential',lambda _: 'SYNTHETIC_NOT_A_CREDENTIAL'),\
                     patch('urllib.request.build_opener',lambda *args:Opener()):
                    transport.worker(request,response)
                assert len(calls)==seq
                assert response.read_bytes()==original_reply
            assert calls[0]['body']['text']['format']['name']=='PrimerResponse'
            assert calls[1]['body']['text']['format']=={'type':'json_object'}
            assert [x['timeout'] for x in calls]==[120,120,30]
            assert all(x['authorization_is_synthetic'] for x in calls)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        probe.RUN,probe.LIMITS,probe.validate_payload=old_run,old_limits,old_validate
    return {'worker_http_opener_calls':3,'real_network_calls':0,'actual_credential_reads':0,
            'primer_schema_preserved':True,'local_json_mode_preserved':True,'embedding_validator_no_recursion':True,
            'duplicate_dispatch_prevented':True,'timeouts':[120,120,30]}
