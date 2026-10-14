"""One-shot worker bridge. Credential reads occur only in the live child worker.

Offline tests replace dispatch; this module has no networking on import.
Authorization and an independently reviewed implementation hash gate live use.
"""
import argparse
from pathlib import Path
import os
import subprocess
import sys
import time
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
PILOT=HERE.parents[1]
ROOT=PILOT.parents[1]
sys.path.insert(0,str(PILOT))
from bounded import Halt,read,file_sha,LIMITS,CARRY,generation_body

REQUIRED_IMPLEMENTATION={
    'research/pilot/strategy-routing/runtime/'+name for name in
    ('bounded.py','official.py','transport.py','runner.py','recovery.py','supervisor-incident.json','authorization.json','input-manifest.json')
}|{'research/pilot/'+name for name in
    ('probe_runtime.py','code_prompt_transport.py','full_retrieve.py','baselines.py',
     'code_prompt_experiment.py','full_index.py','full_runtime.py')}


def check_authorization():
    approval=read(HERE/'authorization.json')
    if approval['human_reply_utc']!='2026-10-14T03:57:08+00:00' or approval['human_reply']!='允许' or approval['approved_change']['generation_reservations_new']!=1883:
        raise Halt('authorization_mismatch',fatal=True)
    review=HERE/'live-readiness.json'
    if not review.exists():raise Halt('offline_review_not_complete',fatal=True)
    verified=read(review)
    if verified.get('status')!='independent_review_passed':raise Halt('offline_review_not_complete',fatal=True)
    if not REQUIRED_IMPLEMENTATION<=set(verified.get('implementation_sha256',{})):raise Halt('incomplete_review_manifest',fatal=True)
    for name,sha in verified['implementation_sha256'].items():
        if file_sha(ROOT/name)!=sha:raise Halt('reviewed_implementation_changed',fatal=True)
    frozen=read(HERE.parent/'freeze.json')
    for name,sha in frozen['sha256'].items():
        if file_sha(ROOT/name)!=sha:raise Halt('frozen_protocol_changed',fatal=True)
    for name,sha in read(HERE/'input-manifest.json')['sha256'].items():
        if file_sha(ROOT/name)!=sha:raise Halt('reviewed_input_changed',fatal=True)
    if file_sha(ROOT/'.cache/pilot/code-prompt-20261013/summary.json')!=read(HERE.parent/'preflight.json')['paid_ledger_sha256_unchanged']:
        raise Halt('prior_paid_ledger_changed',fatal=True)


def validate_payload(service,body):
    if service=='embedding':
        if (set(body)!={'model','input','dimensions','encoding_format'} or body['model']!='text-embedding-3-large'
            or body['dimensions']!=3072 or body['encoding_format']!='float' or not isinstance(body['input'],list)
            or len(body['input'])!=1 or not isinstance(body['input'][0],str) or not body['input'][0].strip()):
            raise Halt('unexpected_embedding_payload',fatal=True)
        return
    if service!='generation':raise Halt('invalid_service',fatal=True)
    try:
        msgs=[{'role':m['role'],'content':m['content'][0]['text']} for m in body['input']]
        fmt=body.get('text',{}).get('format')
        if body!=generation_body(msgs,fmt):raise Halt('unexpected_generation_payload',fatal=True)
        if fmt is not None and fmt not in ({'type':'json_object'},):
            from graphrag.query.structured_search.drift_search.primer import PrimerResponse
            schema=PrimerResponse.model_json_schema();schema['additionalProperties']=False
            expected={'type':'json_schema','name':'PrimerResponse','strict':True,'schema':schema}
            if fmt!=expected:raise Halt('unregistered_query_schema',fatal=True)
    except (KeyError,TypeError,IndexError):raise Halt('malformed_generation_payload',fatal=True) from None

class Transport:
    check_authorization=staticmethod(check_authorization)
    def dispatch(self,request,response,seconds):
        import probe_runtime as probe
        check_authorization()
        result=probe.supervise([sys.executable,str(Path(__file__).resolve()),'worker',str(request),str(response)],seconds+2,float('inf'))
        marker=response.with_suffix('.dispatch.json')
        dispatched=marker.exists() and read(marker).get('dispatch_started') is True
        if response.exists():return {**read(response),'request_dispatched':dispatched}
        # Supervisor-confirmed killed timeout may consume an authorized retry;
        # arbitrary crashes have unknown outcome and are not automatically retried.
        return {'error_category':'request_or_batch_timeout' if result['supervisor_reason']=='request_or_batch_timeout' else 'uncertain_worker_outcome',
                'usage':None,'request_dispatched':dispatched}

def worker(request,response):
    check_authorization()
    import probe_runtime as probe
    import code_prompt_transport
    run=request.parent
    if run.resolve()!= (ROOT/'.cache/pilot/strategy-routing-20261014').resolve():raise Halt('worker_run_directory_mismatch',fatal=True)
    if response.exists():return  # Preserve a reply completed before supervisor crash.
    state=read(run/'summary.json')
    if state['synthetic'] or state['limits']!=LIMITS or state['carry']!=CARRY:raise Halt('worker_budget_mismatch',fatal=True)
    probe.RUN=run;probe.LIMITS={'generation_request_seconds':120,'embedding_request_seconds':30}
    probe.validate_payload=validate_payload
    code_prompt_transport.run(SimpleNamespace(worker=probe.worker),probe,request,response)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['worker']);parser.add_argument('request',type=Path);parser.add_argument('response',type=Path)
    args=parser.parse_args();worker(args.request,args.response)
