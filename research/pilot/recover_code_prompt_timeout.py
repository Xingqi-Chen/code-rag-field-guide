"""One specific event-75 recovery, only after explicit user retry approval.

Inspection is offline. Authorization records and resume are separate actions;
neither the original run nor a later unknown request is automatically retried.
No time window or cumulative budget is reset.
"""
import argparse
import asyncio
import os
import sys

import code_prompt_experiment as variant


def inspect():
    variant.configure()
    variant.check_frozen()
    runtime = variant.CodeRuntime(offline=True)
    state, run = runtime.ledger, variant.RUN
    expected = variant.read(variant.OUT/'timeout-diagnosis.json')
    assert state['status']=='stopped' and state['stop_reason']=='worker_wall_timeout'
    assert len(state['events'])==state['index_generation_attempts']==75
    assert state['embedding_attempts']==0 and state['embedding_reserved_tokens']==206333
    assert state['events'][-1]['request_body_sha256']==expected['unknown_request_body_sha256']
    assert state['events'][-1]['status']=='failed'
    envelope=variant.read(run/'response-75.json')
    assert envelope['error_category']=='worker_wall_timeout' and 'response' not in envelope
    task=variant.read(run/'request-75.json')
    assert variant.probe.digest(variant.probe.canonical(task['body']).encode())==expected['unknown_request_body_sha256']
    assert len(expected['cache_verification'])==74
    for event,item in zip(state['events'][:-1],expected['cache_verification'],strict=True):
        seq=event['sequence'];assert event['status']=='validated' and seq==item['sequence']
        request=variant.read(run/f'request-{seq:02}.json')
        reply=variant.read(run/f'response-{seq:02}.json')['response']
        body=request['body'];variant.transport.validate_payload('generation',body)
        variant.transport.validate_completion(reply,runtime.oenc)
        digest=variant.probe.digest(variant.probe.canonical(body).encode())
        assert digest==event['request_body_sha256']==item['request_body_sha256']
        messages=[{'role':m['role'],'content':m['content'][0]['text']} for m in body['input']]
        schema=body.get('text',{}).get('format',{}).get('schema')
        key=variant.transport.completion_key(messages,schema)
        assert key==item['cache_key']
        cache=run/'completion-cache'/f'{key}.json'
        assert variant.sha(cache)==item['cache_sha256'] and variant.read(cache)['response']==reply
    return runtime,expected


def authorize(confirmed):
    assert confirmed, 'Explicit user approval of this unknown retry is required'
    runtime,expected=inspect()
    state,run=runtime.ledger,variant.RUN
    assert not (run/'stopped-01.json').exists() and not state.get('recoveries')
    assert runtime.remaining_seconds()>60, 'Original wall deadline has expired; no new window is authorized here'
    variant.probe.save(run/'stopped-01.json',state)
    os.rename(run/'output',run/'partial-index-at-stop-01')
    state.setdefault('recoveries',[]).append({'time_utc':variant.transport.now(),'event':75,
        'reason':'worker_wall_timeout_without_complete_response',
        'explicit_one_time_retry_authorized':True,
        'authorization_scope':'User explicitly approved one exact event-75 retry and continuation; no new time window or cumulative budget.',
        'remote_completion_and_cost_unknown':True,'successful_responses_reused':74,
        'snapshot':'stopped-01.json','retry_request_body_sha256':expected['unknown_request_body_sha256']})
    state['verified_resume_ready']=True;state['verified_resume_number']=1
    runtime.save()
    print('One specific retry is ready; 74 successful responses preserved. No model call made by authorization preparation.')


async def resume():
    variant.configure();variant.check_frozen()
    state=variant.read(variant.RUN/'summary.json')
    assert state['verified_resume_ready'] and state['verified_resume_number']==1
    assert len(state['events'])==75 and len(state['recoveries'])==1
    recovery=state['recoveries'][0]
    assert recovery['event']==75 and recovery['explicit_one_time_retry_authorized'] and 'retry_event' not in recovery
    return await variant.full_index.index(resume=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['inspect','authorize','resume'])
    parser.add_argument('--user-approved-specific-retry',action='store_true')
    args=parser.parse_args()
    if args.action=='inspect':
        runtime,_=inspect()
        print(f'74 successful caches verified; request75 result unknown; remaining original window {runtime.remaining_seconds():.1f}s. No state changed or model called.')
    elif args.action=='authorize':authorize(args.user_approved_specific_retry)
    else:sys.exit(asyncio.run(resume()))
