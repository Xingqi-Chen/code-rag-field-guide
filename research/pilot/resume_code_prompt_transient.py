"""User-approved unified transient recovery for this fixed run.

Human approval:2026-10-14 00:24:02 UTC. No successful reply may be replayed
and no cumulative budget may be reset. Previous503-only entry remains in Git history.
"""
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import subprocess
import sys

import resume_code_prompt_http520 as previous
import math

bounded,variant=previous.bounded,previous.variant
POLICY={**previous.POLICY,
    'user_authorized_utc':'2026-10-14T00:24:02+00:00',
    'scope':'This fixed run only: timeout, transient connection errors, HTTP429 and5xx share at most two extra physical attempts per request. Respect Retry-After; never retry authentication, permission, billing, quota, safety or budget failures. Original cumulative caps and120-second request timeout remain; no total deadline.',
    'retry_only':['timeout','transient_connection_error','http429','http5xx'],
    'no_retry':['authentication','permission','billing','quota','safety','budget','TLS_security','other_errors'],
    'unified_transient_retries':True,
    'retry_after':'Wait at least the valid server Retry-After and local5/15-second backoff; malformed header stops.'}
DENIED={'invalid_api_key','authentication_error','authentication_related','permission_denied','permission_related',
    'insufficient_quota','quota_related','billing_related','safety_related','transport_security_error'}


def eligibility(state):
    if state.get('status')!='stopped' or not state.get('events'):return None
    event=state['events'][-1]
    if event.get('request_dispatched') is False:return None
    category=event.get('error_category');status=event.get('http_status')
    if category in DENIED or status in {401,402,403} or event.get('retry_after_invalid'):return None
    if state.get('stop_reason') in {'generation_attempt_limit','generation_input_limit','embedding_dollar_limit','embedding_input_or_attempt_limit'}:return None
    if event.get('status') not in {'failed','uncertain_no_response'}:return None
    temporary=(category in {'worker_wall_timeout','request_or_batch_timeout','transient_connection_error'}
        or event.get('supervisor_reason')=='request_or_batch_timeout'
        or status==429 or isinstance(status,int) and 500<=status<=599)
    if not temporary:return None
    attempts=[e for e in state['events'] if e.get('request_dispatched') is not False
        and e['request_body_sha256']==event['request_body_sha256']]
    if len(attempts)>=3 or any(e['status']=='validated' for e in attempts):return None
    delay=POLICY['backoff_seconds'][len(attempts)-1]
    if 'retry_not_before_utc' in event:
        until=datetime.fromisoformat(event['retry_not_before_utc'])
        delay=max(delay,(until-datetime.now(until.tzinfo)).total_seconds())
    if not math.isfinite(delay) or delay<0:return None
    return {'event':event,'retry_number':len(attempts),'delay_seconds':delay,
        'reason':'user_authorized_unified_transient_retry'}


def install():
    bounded.POLICY=POLICY;bounded.eligibility=eligibility


def controller(approved,approval_utc):
    assert approved and approval_utc==POLICY['user_authorized_utc'],'The recorded human approval is required'
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
            'explicit_unified_transient_approval_confirmed':True,'cumulative_budgets_reset':False,
            'request_payload_changed':False,'successful_generation_cache_entries_verified':615,
            'prior_usage_remains_unknown':True,'total_deadline_reintroduced':False}
        assert not (variant.RUN/'transient-retry-amendment.json').exists()
        variant.write(variant.RUN/'before-transient-retry-amendment.json',state)
        state.setdefault('limit_amendments',[]).append(amendment)
        state['timeout_retry_policy']=POLICY
        state['transient_human_approval_utc']=approval_utc
        state['transient_approval_recorded_utc']=amendment['applied_utc']
        runtime.save()
        variant.write(variant.RUN/'transient-retry-amendment.json',amendment)
        variant.write(variant.OUT/'transient-retry-amendment.json',amendment)
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
    parser.add_argument('--user-approved-transient-recovery',action='store_true')
    parser.add_argument('--human-approval-utc');args=parser.parse_args()
    if args.action=='continue':sys.exit(controller(args.user_approved_transient_recovery,args.human_approval_utc))
    else:install();sys.exit(asyncio.run(bounded.resume_worker()))
