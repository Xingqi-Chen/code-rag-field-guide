"""Offline preparation for the explicitly approved one-time event-159 retry.

The failed remote call may still have incurred cost. This does not cancel it or
invent its result. Never invokes a provider; successful replies must match cache.
"""
import argparse
import json
import os

import full_runtime as full
import probe_runtime as probe


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--authorize-one-uncertain-retry',action='store_true',required=True)
    parser.parse_args()
    runtime=full.Runtime(offline=True)
    state,run=runtime.ledger,full.RUN
    if (state['status']!='stopped' or state['stop_reason']!='worker_wall_timeout'
            or len(state['events'])!=159 or state['index_generation_attempts']!=159):
        raise full.Halt('not_the_diagnosed_event_159_timeout')
    # The old window expired overnight. The user explicitly authorized a new
    # recovery window; it begins only when the actual resume process starts.
    if (run/'stopped-02.json').exists():raise full.Halt('recovery_already_attempted')
    for event in state['events'][:-1]:
        seq=event['sequence']
        if event['status']!=('invalid_response' if seq==14 else 'validated'):
            raise full.Halt('unrecognized_prior_event')
        task=json.loads((run/f'request-{seq:02}.json').read_text())
        envelope=json.loads((run/f'response-{seq:02}.json').read_text())
        body,reply=task['body'],envelope['response']
        if task['service']!='generation' or envelope['http_status']!=200:
            raise full.Halt('unexpected_prior_service_or_status')
        full.validate_payload('generation',body)
        full.validate_completion(reply,runtime.oenc)
        if probe.digest(probe.canonical(body).encode())!=event['request_body_sha256']:
            raise full.Halt('request_digest_mismatch')
        messages=[{'role':m['role'],'content':m['content'][0]['text']} for m in body['input']]
        schema=body.get('text',{}).get('format',{}).get('schema')
        cache=run/'completion-cache'/f'{full.completion_key(messages,schema)}.json'
        if not cache.exists() or json.loads(cache.read_text())['response']!=reply:
            raise full.Halt('successful_response_cache_mismatch')
    last=state['events'][-1]
    envelope=json.loads((run/'response-159.json').read_text())
    task=json.loads((run/'request-159.json').read_text())
    if (envelope!={'error_category':'worker_wall_timeout'} or last['status']!='failed'
            or last['error_category']!='worker_wall_timeout'
            or probe.digest(probe.canonical(task['body']).encode())!=last['request_body_sha256']):
        raise full.Halt('timeout_identity_mismatch')
    probe.save(run/'stopped-02.json',state)
    os.rename(run/'output',run/'partial-index-at-stop-02')
    state.setdefault('recoveries',[]).append({'time_utc':full.now(),'event':159,
        'reason':'worker_wall_timeout_without_complete_response',
        'explicit_one_time_retry_authorized':True,
        'authorization_date_utc':'2026-10-13T00:24:00+00:00',
        'new_recovery_window_seconds':7200,
        'remote_completion_and_cost_unknown':True,
        'successful_responses_reused':158,'snapshot':'stopped-02.json',
        'retry_request_body_sha256':last['request_body_sha256']})
    state['verified_resume_ready']=True
    state['verified_resume_number']=2
    state['pending_recovery_window_seconds']=7200
    runtime.save()
    print(json.dumps({'offline_recovery_ready':True,'successful_cached_replies':158,
                      'uncertain_request_to_retry_once':159,'additional_provider_calls':0}))


if __name__=='__main__':main()
