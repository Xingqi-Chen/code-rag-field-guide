"""Recover the complete event554 reply after executor transport loss.

No replay of554. Offline preparation preserves the stale ledger verbatim and
validates the response before adding it to the exact payload cache. Continued
indexing uses the already approved limits and timeout/HTTP520 retry policy.
"""
import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys

import resume_code_prompt_http520 as current

variant=current.variant
bounded=current.bounded


def prepare():
    variant.configure();variant.check_frozen()
    before=variant.read(variant.RUN/'summary.json')
    assert before['status']=='running' and len(before['events'])==554
    try:os.kill(before['supervisor_pid'],0)
    except ProcessLookupError:pass
    else:raise RuntimeError('Prior supervisor still exists; refuse recovery')
    runtime=variant.CodeRuntime(offline=True)
    try:
        state=runtime.ledger;event=state['events'][-1]
        assert state['timeout_retry_policy']==current.POLICY
        assert event['status']=='reserved_before_dispatch'
        assert event['request_body_sha256']=='bd6edcfabfea89b89c5c54984ba9a78ad5297661c807b5044b72d64666b222be'
        assert len(state['recoveries'])==7 and not state['verified_resume_ready']
        assert bounded.verify_successful_cache(runtime)==546
        request=variant.read(variant.RUN/'request-554.json')
        envelope=variant.read(variant.RUN/'response-554.json')
        dispatch=variant.read(variant.RUN/'response-554.dispatch.json')
        assert request['service']=='generation' and envelope['http_status']==200
        assert dispatch=={'dispatch_slot_claimed':True,'dispatch_started':True}
        body=request['body'];reply=envelope['response']
        assert variant.sha_body(body)==event['request_body_sha256']
        variant.transport.validate_payload('generation',body)
        content,usage=variant.transport.validate_completion(reply,runtime.oenc)
        messages=[{'role':m['role'],'content':m['content'][0]['text']} for m in body['input']]
        key=variant.transport.completion_key(messages,body.get('text',{}).get('format',{}).get('schema'))
        cache=variant.RUN/'completion-cache'/f'{key}.json'
        assert not cache.exists()
        snapshot=variant.RUN/'before-host-recovery-554.json'
        stop=variant.RUN/'stopped-08.json'
        assert not snapshot.exists() and not stop.exists()
        variant.write(snapshot,before)
        detected=variant.transport.now()
        state.update(status='stopped',stop_reason='executor_transport_loss_complete_reply_recovered',stopped_utc=detected)
        state['host_interruption_timing']={
            'last_request_started_utc':event['started_utc'],'absence_detected_utc':detected,
            'actual_process_end_utc':None,'event554_supervised_seconds':None,
            'note':'Process absent and lock free at inspection. Detection time is an upper bound on process end; active workflow timing includes an unknown inactive interval.'}
        variant.write(stop,state)
        os.rename(variant.RUN/'output',variant.RUN/'partial-index-at-stop-08')
        variant.write(cache,{'response':reply,'origin':f'{variant.RUN.name}/response-554.json'})
        event.update({k:v for k,v in envelope.items() if k!='response'})
        event.update(status='validated',usage=usage,request_dispatched=True,
            visible_output_common_tokens=len(runtime.oenc.encode(content)),
            requested_output_limit_exceeded=usage['completion_tokens']>2048 or len(runtime.oenc.encode(content))>2048,
            validation_stage='offline_recovery_after_executor_transport_loss',
            validated_utc=detected,original_ledger_status='reserved_before_dispatch')
        recovery={'time_utc':detected,'event':554,'reason':'complete_reply_not_committed_before_executor_transport_loss',
            'response_reused_without_resending':True,'original_status':'reserved_before_dispatch',
            'visible_output_common_tokens':event['visible_output_common_tokens'],'usage':usage,
            'successful_responses_reused':547,'snapshot':stop.name,
            'original_ledger_snapshot':snapshot.name,'new_calls_for_recovery':0,
            'response_sha256':variant.sha(variant.RUN/'response-554.json'),
            'request_body_sha256':event['request_body_sha256'],
            'cache_sha256':variant.sha(cache),'request_elapsed_seconds':None}
        state['recoveries'].append(recovery)
        state['verified_resume_ready']=True;state['verified_resume_number']=8
        assert bounded.verify_successful_cache(runtime)==547
        runtime.save()
        variant.write(variant.OUT/'host-recovery-554.json',{'recovery':recovery,
            'timing_uncertainty':state['host_interruption_timing'],'event':event,
            'cumulative_caps_reset':False,'policy_changed':False,'imported_vectors_verified':134})
        print('Recovered complete554 reply offline;547 successful responses and134 imported vectors verified. No replay.')
    finally:runtime._lock_file.close()


async def worker():
    variant.configure();variant.check_frozen();current.install()
    state=variant.read(variant.RUN/'summary.json')
    assert state['verified_resume_ready'] and state['verified_resume_number']==8
    assert state['recoveries'][-1]['response_reused_without_resending']
    assert state['events'][-1]['sequence']==554 and state['events'][-1]['status']=='validated'
    return await variant.full_index.index(resume=True)


def controller():
    result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker'])
    current.install()
    while True:
        state=variant.read(variant.RUN/'summary.json')
        if result.returncode==0 and state['status']=='index_complete':return 0
        if state['status']!='stopped' or not bounded.prepare_recovery():return 1
        result=subprocess.run([sys.executable,str(Path(current.__file__).resolve()),'resume-worker'])
        if not bounded.bind_retry_event():return 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','continue','worker']);args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='worker':sys.exit(asyncio.run(worker()))
    else:sys.exit(controller())
