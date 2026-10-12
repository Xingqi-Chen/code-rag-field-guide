"""One diagnosed recovery: complete event 14 exceeded requested output usage.

Offline only. Never contacts a service. It preserves the stopped ledger and
partial index, validates every known reply, then permits one explicit resume.
"""
import json
import os

import full_runtime as full
import probe_runtime as probe


def main():
    runtime = full.Runtime(offline=True)
    state, run = runtime.ledger, full.RUN
    if (state['status'] != 'stopped' or len(state['events']) != 14
            or state['index_generation_attempts'] != 14 or state.get('verified_resume_ready')):
        raise full.Halt('not_the_diagnosed_output_limit_stop')
    snapshot = run/'stopped-01.json'
    if snapshot.exists():
        raise full.Halt('recovery_already_attempted')
    validated = []
    for event in state['events']:
        seq = event['sequence']
        if event['status'] != ('invalid_response' if seq == 14 else 'validated'):
            raise full.Halt('unknown_or_uncertain_event_blocks_resume')
        request = json.loads((run/f'request-{seq:02}.json').read_text())
        envelope = json.loads((run/f'response-{seq:02}.json').read_text())
        body, reply = request['body'], envelope['response']
        if request['service'] != 'generation' or envelope['http_status'] != 200:
            raise full.Halt('unexpected_recovery_service_or_status')
        full.validate_payload('generation', body)
        content, usage = full.validate_completion(reply, runtime.oenc)
        if probe.digest(probe.canonical(body).encode()) != event['request_body_sha256']:
            raise full.Halt('request_digest_mismatch')
        if seq == 14 and not (usage['completion_tokens']==2278 and len(runtime.oenc.encode(content))==1220):
            raise full.Halt('diagnosed_reply_identity_mismatch')
        messages = [{'role': m['role'], 'content': m['content'][0]['text']} for m in body['input']]
        schema = body.get('text',{}).get('format',{}).get('schema')
        validated.append((full.completion_key(messages,schema), reply, seq))
    probe.save(snapshot, state)
    for key, reply, seq in validated:
        probe.save(run/'completion-cache'/f'{key}.json',
                   {'response': reply, 'origin': f'{run.name}/response-{seq:02}.json'})
    os.rename(run/'output', run/'partial-index-at-stop-01')
    state.setdefault('executions', []).append({'stage':'index', 'resume':False,
        'source_commit':state['source_commit'], 'started_utc':state['started_utc'],
        'next_event_sequence':1, 'last_event_sequence':14})
    state['recoveries'] = [{'time_utc': full.now(), 'event':14,
        'reason':'completed_reply_exceeded_requested_output_cap',
        'previous_validation_failure':'reported_or_visible_output_cap_exceeded',
        'response_reused_without_resending':True, 'usage':validated[-1][1]['usage'],
        'visible_output_common_tokens':1220,
        'original_stop_reason_overwritten_by_pending_async_tasks':state['stop_reason'],
        'snapshot':'stopped-01.json'}]
    state['verified_resume_ready'] = True
    runtime.save()
    print(json.dumps({'offline_recovery_ready':True, 'exact_completed_response_cache_items':14,
                      'additional_provider_calls':0}))


if __name__ == '__main__': main()
