"""Authorized120-second continuation; exactly one exception for logical107.

This amends only the client generation wait, records an explicit policy boundary,
and retains every attempt, cache, cumulative cap and the original wall deadline.
"""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys

import resume_code_prompt_bounded as bounded

variant=bounded.variant
OLD_POLICY=dict(bounded.POLICY)
EXHAUSTED_HASH='824657e6c6f95af4c7c8c031c9e12edd10e05e6ae2d7c34997a074b5f7156fdc'
POLICY={**OLD_POLICY,
    'generation_request_seconds':120,
    'scope':'Continue this code-prompt run at120 seconds. Exactly one further attempt for logical107; stop if it fails. Other logical requests retain at most two additional timeout attempts.',
    'one_time_exhausted_request_exception':{'original_event':107,'prior_attempts':[107,108,109],
        'request_body_sha256':EXHAUSTED_HASH,'only_next_event':110,'extra_attempts':1},
}
original_eligibility=bounded.eligibility


def eligibility(state):
    if state.get('status')=='stopped' and state.get('stop_reason')=='worker_wall_timeout' and len(state.get('events',[]))==109:
        last=state['events'][-1]
        matching=[e for e in state['events'] if e['request_body_sha256']==EXHAUSTED_HASH]
        if last['sequence']==109 and last['request_body_sha256']==EXHAUSTED_HASH and [e['sequence'] for e in matching]==[107,108,109] and all(e['status']=='failed' and e.get('error_category')=='worker_wall_timeout' for e in matching):
            return {'event':last,'retry_number':3,'delay_seconds':5}
    return original_eligibility(state)


def install_policy():
    bounded.POLICY=POLICY
    bounded.eligibility=eligibility


def controller(approved):
    assert approved,'Existing task authorization and120-second continuation instruction are required'
    variant.configure();variant.check_frozen()
    runtime=variant.CodeRuntime(offline=True)
    try:
        state=runtime.ledger
        assert eligibility(state) is not None
        assert len(state['events'])==109 and len(state['recoveries'])==4
        assert state['timeout_retry_policy']==OLD_POLICY and not state.get('verified_resume_ready')
        assert state['started_utc']=='2026-10-13T13:12:59.674100+00:00' and 'window_deadline_utc' not in state
        assert state['limits']['generation_request_seconds']==60
        assert runtime.remaining_seconds()>127
        assert bounded.verify_successful_cache(runtime)==104
        amendment={'applied_utc':variant.transport.now(),'prior_generation_request_seconds':60,
            'generation_request_seconds':120,'first_possible_event':110,
            'original_deadline_utc':POLICY['original_deadline_utc'],
            'human_standing_timeout_authorization_utc':POLICY['user_authorized_utc'],
            'execution_instruction':'Parent delegation explicitly authorized120-second recovery and one further attempt for logical107 under existing user authorization.',
            'request_body_prompt_model_corpus_parser_and_metrics_changed':False,
            'cumulative_caps_reset':False,'deadline_extended':False,
            'comparison_limit':'Mixed60/120-second execution and amended retry policy; completion, latency, cost or downstream graph differences cannot be attributed solely to prompt/types.',
            'policy':POLICY}
        path=variant.RUN/'timeout-amendment-120.json'
        assert not path.exists()
        variant.write(variant.RUN/'before-timeout-amendment-120.json',state)
        variant.write(path,amendment)
        variant.write(variant.OUT/'timeout-amendment-120.json',amendment)
        state.setdefault('limit_amendments',[]).append(amendment)
        state['timeout_retry_policy']=POLICY
        state['limits']={**state['limits'],'generation_request_seconds':120}
        runtime.save()
    finally:
        runtime._lock_file.close()
    install_policy()
    while bounded.prepare_recovery():
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--resume-worker'])
        if not bounded.bind_retry_event():return 1
        state=variant.read(variant.RUN/'summary.json')
        if result.returncode==0 and state['status']=='index_complete':return 0
        if result.returncode==0 or state['status']!='stopped':return 1
    return 1


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--approved-120-second-continuation',action='store_true')
    parser.add_argument('--resume-worker',action='store_true')
    args=parser.parse_args()
    if args.resume_worker:
        install_policy()
        sys.exit(asyncio.run(bounded.resume_worker()))
    sys.exit(controller(args.approved_120_second_continuation))
