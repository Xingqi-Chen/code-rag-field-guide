"""Prepared, not authorized: bounded HTTP503/model_related recovery.

Requires separate user approval. The same physical-attempt cap is shared with
timeouts and HTTP520; no successful reply may be replayed or budget reset.
"""
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import subprocess
import sys

import resume_code_prompt_http520 as previous

bounded,variant=previous.bounded,previous.variant
POLICY={**previous.POLICY,
    'scope':'This code-prompt run only: after separate approval, HTTP503/model_related shares the existing maximum two extra physical attempts per exact request with timeout and HTTP520. No total deadline; original cumulative budgets and120-second request timeout remain.',
    'retry_only':[*previous.POLICY['retry_only'],'model_related_with_http503'],
    'no_retry':['authentication','permission','budget','other_errors_except_timeout_http520_and_model_related_http503'],
    'http503_retry_extension':{'http_status':503,'error_category':'model_related',
        'max_additional_retries_per_request_hash':2,'shared_with_timeout_and_http520':True}}


def eligibility(state):
    events=[e for e in state.get('events',[]) if e.get('request_dispatched') is not False]
    if state.get('status')=='stopped' and events:
        event=events[-1]
        if (state.get('stop_reason')==event.get('error_category')=='model_related'
                and event.get('http_status')==503 and event.get('status')=='failed'):
            attempts=[e for e in events if e['request_body_sha256']==event['request_body_sha256']]
            if len(attempts)>=3 or any(e['status']=='validated' for e in attempts):return None
            return {'event':event,'retry_number':len(attempts),'delay_seconds':POLICY['backoff_seconds'][len(attempts)-1]}
    return previous.eligibility(state)


def install():
    bounded.POLICY=POLICY;bounded.eligibility=eligibility


def controller(approved,approval_utc):
    assert approved and approval_utc,'Separate explicit human approval and its UTC timestamp required'
    approval=datetime.fromisoformat(approval_utc)
    assert approval.utcoffset() is not None and approval.utcoffset().total_seconds()==0
    assert approval>=datetime.fromisoformat('2026-10-13T16:53:03.731563+00:00')
    variant.configure();variant.check_frozen()
    runtime=variant.CodeRuntime(offline=True)
    try:
        state=runtime.ledger
        assert state['status']=='stopped' and len(state['events'])==623
        assert state['timeout_retry_policy']==previous.POLICY and state['wall_deadline_removed']
        event=state['events'][-1]
        assert event['request_body_sha256']=='a3cb9f3c3a2f85c41320de1d05dd5a77d7da7c6b02b59a83507172b8c0f6c56c'
        assert eligibility(state)['retry_number']==1
        assert bounded.verify_successful_cache(runtime)==615
        amendment={'applied_utc':variant.transport.now(),'first_possible_event':624,
            'trigger_event':623,'policy':POLICY,'human_approval_utc':approval_utc,
            'explicit_separate_http503_approval_confirmed':True,'cumulative_budgets_reset':False,
            'request_payload_changed':False,'successful_generation_cache_entries_verified':615,
            'prior_usage_remains_unknown':True,'total_deadline_reintroduced':False}
        assert not (variant.RUN/'http503-retry-amendment.json').exists()
        variant.write(variant.RUN/'before-http503-retry-amendment.json',state)
        state.setdefault('limit_amendments',[]).append(amendment)
        state['timeout_retry_policy']=POLICY
        state['http503_human_approval_utc']=approval_utc
        state['http503_approval_recorded_utc']=amendment['applied_utc']
        runtime.save()
        variant.write(variant.RUN/'http503-retry-amendment.json',amendment)
        variant.write(variant.OUT/'http503-retry-amendment.json',amendment)
    finally:runtime._lock_file.close()
    install()
    while bounded.prepare_recovery():
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'resume-worker'])
        if not bounded.bind_retry_event():return 1
        state=variant.read(variant.RUN/'summary.json')
        if result.returncode==0 and state['status']=='index_complete':return 0
        if result.returncode==0 or state['status']!='stopped':return 1
    return 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['continue','resume-worker'])
    parser.add_argument('--user-approved-http503-recovery',action='store_true')
    parser.add_argument('--human-approval-utc');args=parser.parse_args()
    if args.action=='continue':sys.exit(controller(args.user_approved_http503_recovery,args.human_approval_utc))
    else:install();sys.exit(asyncio.run(bounded.resume_worker()))
