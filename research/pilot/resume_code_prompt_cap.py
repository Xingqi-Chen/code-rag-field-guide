"""User-approved1200→1600 generation reservations; other caps unchanged."""
import argparse
from pathlib import Path
import os
import subprocess
import sys

import resume_code_prompt_transient as current

variant,bounded=current.variant,current.bounded
APPROVAL='2026-10-14T00:31:24+00:00'


def checkpoint_request():
    state=variant.read(variant.RUN/'summary.json')
    assert state['status']=='running' and state['limits']['generation_index_attempts']==1200
    request={'human_approval_utc':APPROVAL,'requested_utc':variant.transport.now(),
        'previous_generation_cap':1200,'generation_cap':1600,'other_caps_unchanged':True,
        'checkpoint':'Finish the in-flight request, pause next reservation before dispatch, then resume exact cached results.'}
    assert not (variant.RUN/'generation-cap-request.json').exists()
    variant.write(variant.RUN/'generation-cap-request.json',request)
    variant.write(variant.OUT/'generation-cap-request.json',request)


def prepare():
    variant.configure();variant.check_frozen();runtime=variant.CodeRuntime(offline=True)
    try:
        s=runtime.ledger;e=s['events'][-1];seq=e['sequence']
        assert s['status']=='stopped' and s['stop_reason']=='authorized_generation_cap_checkpoint'
        assert e['request_dispatched'] is False and e['policy_checkpoint']
        assert not (variant.RUN/f'response-{seq:02}.dispatch.json').exists()
        assert s['limits']['generation_index_attempts']==1200 and s['timeout_retry_policy']==current.POLICY
        count=bounded.verify_successful_cache(runtime)
        number=len(s['recoveries'])+1;snapshot=variant.RUN/f'stopped-{number:02}.json'
        assert not snapshot.exists() and not (variant.RUN/'generation-cap-amendment.json').exists()
        variant.write(snapshot,s)
        os.rename(variant.RUN/'output',variant.RUN/f'partial-index-at-stop-{number:02}')
        previous=dict(s['limits']);s['limits']={**previous,'generation_index_attempts':1600}
        amendment={'human_approval_utc':APPROVAL,'applied_utc':variant.transport.now(),
            'previous_generation_cap':1200,'generation_cap':1600,'non_dispatched_checkpoint_event':seq,
            'first_possible_event':seq+1,'previous_limits':previous,'new_limits':s['limits'],
            'successful_generation_cache_entries_verified':count,'imported_vectors_verified':134,
            'other_caps_unchanged':True,'cumulative_usage_reset':False,'prompt_algorithm_and_query_changes':False}
        s.setdefault('limit_amendments',[]).append(amendment)
        s.setdefault('non_dispatched_checkpoint_events',[]).append(seq)
        s['recoveries'].append({'time_utc':amendment['applied_utc'],'event':seq,'service':e['service'],
            'reason':'authorized_generation_cap_checkpoint_before_dispatch','authorization_utc':APPROVAL,
            'explicit_one_time_retry_authorized':True,'logical_retry_number':0,'backoff_seconds':0,
            'remote_completion_and_cost_unknown':False,'successful_responses_reused':count,
            'snapshot':snapshot.name,'retry_request_body_sha256':e['request_body_sha256']})
        s['verified_resume_ready']=True;s['verified_resume_number']=number
        runtime.save()
        variant.write(variant.RUN/'generation-cap-amendment.json',amendment)
        variant.write(variant.OUT/'generation-cap-amendment.json',amendment)
        print(f'Cap1600 applied;{count} successful responses reused; checkpoint{seq} never dispatched.',flush=True)
    finally:runtime._lock_file.close()


def controller():
    prepare();current.install()
    while True:
        result=subprocess.run([sys.executable,str(Path(current.__file__).resolve()),'resume-worker'])
        if not bounded.bind_retry_event():return 1
        state=variant.read(variant.RUN/'summary.json')
        if result.returncode==0 and state['status']=='index_complete':return 0
        if state['status']!='stopped' or not bounded.prepare_recovery():return 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['checkpoint','continue']);a=p.parse_args()
    if a.action=='checkpoint':checkpoint_request()
    else:sys.exit(controller())
