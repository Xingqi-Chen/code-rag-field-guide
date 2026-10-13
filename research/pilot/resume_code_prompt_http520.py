"""Explicitly approved extension for HTTP520, sharing the existing retry cap.

Prepared offline. The real controller requires separate user approval because
the previously approved policy stopped all non-timeout HTTP errors.
"""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys

import resume_code_prompt_no_deadline as previous

bounded=previous.bounded
variant=previous.variant
POLICY={**previous.POLICY,
    'scope':'This code-prompt run only: retain no total deadline, original cumulative budgets and120-second generation requests. Once separately approved, timeout and HTTP520 outcomes share at most two additional physical attempts per request hash.',
    'http520_retry_extension':{'http_status':520,'max_additional_retries_per_request_hash':2,
        'shared_with_timeout_attempts':True,'other_http_errors_retry':False,
        'scope':'This code-prompt run only; requires separate approval before first use.'}}
POLICY['retry_only']=[*previous.POLICY['retry_only'],'unclassified_http_error_with_http520']
POLICY['no_retry']=[name for name in previous.POLICY['no_retry'] if name!='non_timeout_errors']+['non_timeout_errors_except_explicit_http520']


def eligibility(state):
    events=[e for e in state.get('events',[]) if e.get('request_dispatched') is not False]
    if state.get('status')=='stopped' and events:
        event=events[-1]
        if state.get('stop_reason')=='unclassified_http_error' and event.get('error_category')=='unclassified_http_error' and event.get('http_status')==520 and event.get('status')=='failed':
            attempts=[e for e in events if e['request_body_sha256']==event['request_body_sha256']]
            if len(attempts)>=3 or any(e['status']=='validated' for e in attempts):return None
            return {'event':event,'retry_number':len(attempts),'delay_seconds':POLICY['backoff_seconds'][len(attempts)-1]}
    return previous.eligibility(state)


def install():
    bounded.POLICY=POLICY
    bounded.eligibility=eligibility


def controller(approved):
    assert approved,'Separate user approval for HTTP520 recovery is required'
    variant.configure();variant.check_frozen()
    runtime=variant.CodeRuntime(offline=True)
    try:
        state=runtime.ledger
        assert state['status']=='stopped' and len(state['events'])==272
        assert state['timeout_retry_policy']==previous.POLICY and state['wall_deadline_removed'] is True
        event=state['events'][-1]
        assert event['request_body_sha256']=='17b46a852d4e61e4321bfe32cf59a1fb5df5da1c4e2b3726d3e2356864465f36'
        assert eligibility(state)['retry_number']==1 and event['http_status']==520
        successes=bounded.verify_successful_cache(runtime)
        amendment={'applied_utc':variant.transport.now(),'first_possible_event':273,
            'trigger_event':272,'trigger_http_status':520,'policy':POLICY,
            'cumulative_budgets_reset':False,'total_deadline_reintroduced':False,
            'successful_generation_cache_entries_verified':successes,
            'provider_completion_and_usage_for_272':'Unknown; HTTP520 has no complete model reply or usage.',
            'request_body_prompt_model_corpus_parser_and_metrics_changed':False,
            'explicit_separate_http520_recovery_approval_confirmed':True,
            'approval_time_basis':'applied_utc records approval confirmation/config activation, not the original user-message timestamp.'}
        assert not (variant.RUN/'http520-retry-amendment.json').exists()
        variant.write(variant.RUN/'before-http520-retry-amendment.json',state)
        state.setdefault('limit_amendments',[]).append(amendment)
        state['timeout_retry_policy']=POLICY
        state['http520_approval_recorded_utc']=amendment['applied_utc']
        runtime.save()
        variant.write(variant.RUN/'http520-retry-amendment.json',amendment)
        variant.write(variant.OUT/'http520-retry-amendment.json',amendment)
    finally:
        runtime._lock_file.close()
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
    parser.add_argument('--user-approved-http520-recovery',action='store_true');args=parser.parse_args()
    if args.action=='continue':sys.exit(controller(args.user_approved_http520_recovery))
    else:
        install();sys.exit(asyncio.run(bounded.resume_worker()))
