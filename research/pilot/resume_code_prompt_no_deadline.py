"""Apply the user's removal of only the total wall-clock deadline.

The next reservation of an old process stops before dispatch; the in-flight
request completes normally. All cumulative reservations stay conservative.
"""
import argparse
import asyncio
import copy
import json
from pathlib import Path
import subprocess
import sys

import resume_code_prompt_120 as prior

bounded=prior.bounded
variant=bounded.variant
POLICY={**prior.POLICY,'wall_deadline_removed':True,
    'scope':'User removed the total wall deadline at2026-10-13 15:30 UTC. Continue this run to completion with120-second generation requests, original cumulative budgets, and at most two additional timeout attempts per new logical request.'}
POLICY['unchanged']=[item for item in prior.POLICY['unchanged'] if item!='original_wall_deadline']
POLICY['previous_deadline_utc']=POLICY.pop('original_deadline_utc')
base_eligibility=bounded.eligibility


def eligibility(state):
    if state.get('status')=='stopped' and state.get('stop_reason')=='authorized_deadline_policy_checkpoint':
        event=state['events'][-1]
        if event.get('request_dispatched') is False and event.get('policy_checkpoint') is True:
            return {'event':event,'retry_number':0,'delay_seconds':0}
        return None
    # A never-dispatched administrative reservation is not a physical retry.
    physical=copy.copy(state)
    physical['events']=[e for e in state.get('events',[]) if e.get('request_dispatched') is not False]
    return base_eligibility(physical)


def install():
    bounded.POLICY=POLICY
    bounded.eligibility=eligibility


def request_checkpoint(approved):
    assert approved,'The user explicitly removed the total deadline'
    variant.check_frozen()
    state=variant.read(variant.RUN/'summary.json')
    assert state['status']=='running' and not state.get('wall_deadline_removed')
    path=variant.RUN/'deadline-removal-request.json'
    assert not path.exists()
    request={'requested_utc':variant.transport.now(),'user_instruction_utc_minute':'2026-10-13T15:30Z',
        'instruction':'No overall deadline; continue until complete.',
        'removed':'Only total wall-clock deadline',
        'generation_request_seconds':120,'embedding_request_seconds':30,
        'cumulative_budgets_reset':False,'max_additional_timeout_retries':2,
        'checkpoint':'Finish in-flight request; stop next reservation before network dispatch.'}
    variant.write(path,request)
    variant.write(variant.OUT/'deadline-removal-request.json',request)
    print(json.dumps({'event':'safe_checkpoint_requested','in_flight_request_not_interrupted':True}),flush=True)


def controller(approved):
    assert approved,'The user explicitly removed the total deadline'
    variant.configure();variant.check_frozen()
    runtime=variant.CodeRuntime(offline=True)
    try:
        state=runtime.ledger
        assert state['stop_reason']=='authorized_deadline_policy_checkpoint'
        assert eligibility(state) is not None and not state.get('wall_deadline_removed')
        event=state['events'][-1];seq=event['sequence']
        envelope=variant.read(variant.RUN/f'response-{seq:02}.json')
        assert envelope['policy_checkpoint'] and envelope['request_dispatched'] is False
        assert not (variant.RUN/f'response-{seq:02}.dispatch.json').exists()
        assert state['timeout_retry_policy']==prior.POLICY
        bounded.verify_successful_cache(runtime)
        amendment={'applied_utc':variant.transport.now(),'total_wall_deadline_removed':True,
            'previous_deadline_utc':'2026-10-13T16:12:59.674100+00:00',
            'generation_request_seconds':120,'embedding_request_seconds':30,
            'first_possible_event':seq+1,'non_dispatched_checkpoint_event':seq,
            'cumulative_budgets_reset':False,'policy':POLICY,
            'accounting':'Keep the checkpoint reservation in attempt/input caps conservatively; it made no API request and is not an unknown provider outcome.'}
        variant.write(variant.RUN/'before-deadline-removal.json',state)
        state.setdefault('limit_amendments',[]).append(amendment)
        state['wall_deadline_removed']=True
        state['limits']={**state['limits'],'wall_seconds':None}
        state['timeout_retry_policy']=POLICY
        state.setdefault('non_dispatched_checkpoint_events',[]).append(seq)
        runtime.save()
        variant.write(variant.RUN/'deadline-removal-applied.json',amendment)
        variant.write(variant.OUT/'deadline-removal-applied.json',amendment)
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
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['checkpoint','continue','resume-worker'])
    parser.add_argument('--user-removed-total-deadline',action='store_true')
    args=parser.parse_args()
    if args.action=='checkpoint':request_checkpoint(args.user_removed_total_deadline)
    elif args.action=='continue':sys.exit(controller(args.user_removed_total_deadline))
    else:
        install()
        sys.exit(asyncio.run(bounded.resume_worker()))
