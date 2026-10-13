"""Task-scoped, explicitly authorized timeout recovery; never resets budgets.

Each subprocess runs the frozen index implementation. A stopped timeout gets
an immutable snapshot and one exact request-hash recovery record before replay.
Every logical request has at most two additional physical attempts in total.
"""
import argparse
import asyncio
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import code_prompt_experiment as variant

POLICY = {
    'user_authorized_utc': '2026-10-13T14:44:31+00:00',
    'scope': 'This code-prompt run only: retry107 and later timeout outcomes without repeated permission questions.',
    'max_additional_retries_per_request_hash': 2,
    'backoff_seconds': [5, 15],
    'original_deadline_utc': '2026-10-13T16:12:59.674100+00:00',
    'generation_request_seconds': 60,
    'embedding_request_seconds': 30,
    'unchanged': ['cumulative_attempt_caps', 'cumulative_input_cap', 'cumulative_embedding_dollar_cap', 'original_wall_deadline', 'request_payloads'],
    'retry_only': ['worker_wall_timeout', 'request_or_batch_timeout'],
    'no_retry': ['authentication', 'permission', 'budget', 'non_timeout_errors'],
}


def eligibility(state):
    """Pure decision: never classify an absent HTTP response as a provider error."""
    if state.get('status') != 'stopped' or not state.get('events'):
        return None
    event = state['events'][-1]
    reason = state.get('stop_reason')
    timeout = reason == 'worker_wall_timeout' or (
        reason == 'request_or_batch_timeout' or
        reason == 'uncertain_request_no_automatic_replay'
        and event.get('supervisor_reason') == 'request_or_batch_timeout')
    if not timeout or event['status'] not in {'failed', 'uncertain_no_response'}:
        return None
    attempts = [e for e in state['events'] if e['request_body_sha256'] == event['request_body_sha256']]
    if any(e['status'] == 'validated' for e in attempts) or len(attempts) >= 3:
        return None
    return {'event': event, 'retry_number': len(attempts),
            'delay_seconds': POLICY['backoff_seconds'][len(attempts)-1]}


def verify_successful_cache(runtime):
    imported=variant.read(variant.RUN/'imported-embedding-cache.json')
    assert len(imported)==134
    for item in imported:
        assert variant.sha(variant.RUN/'embedding-cache'/f"{item['cache_key']}.json")==item['cache_sha256']
    count = 0
    for event in runtime.ledger['events']:
        if event['status'] != 'validated':
            continue
        seq = event['sequence']
        task = variant.read(variant.RUN/f'request-{seq:02}.json')
        envelope = variant.read(variant.RUN/f'response-{seq:02}.json')
        body = task['body']
        assert variant.probe.digest(variant.probe.canonical(body).encode()) == event['request_body_sha256']
        service=event['service']
        variant.transport.validate_payload(service, body)
        if service=='embedding':
            texts=body['input']
            variant.probe.validate_embedding(envelope['response'],len(texts),event['input_tokens'])
            for item in envelope['response']['data']:
                key=variant.transport.embedding_key(texts[item['index']])
                assert variant.read(variant.RUN/'embedding-cache'/f'{key}.json')['vector']==item['embedding']
            continue
        assert service=='generation'
        variant.transport.validate_completion(envelope['response'], runtime.oenc)
        messages = [{'role': m['role'], 'content': m['content'][0]['text']} for m in body['input']]
        schema = body.get('text', {}).get('format', {}).get('schema')
        key = variant.transport.completion_key(messages, schema)
        assert variant.read(variant.RUN/'completion-cache'/f'{key}.json')['response'] == envelope['response']
        count += 1
    return count


def prepare_recovery():
    variant.configure(); variant.check_frozen()
    runtime = variant.CodeRuntime(offline=True)
    try:
        state = runtime.ledger
        assert state['timeout_retry_policy'] == POLICY
        decision = eligibility(state)
        if decision is None:
            print(json.dumps({'event': 'paused', 'reason': 'not_timeout_or_retry_limit_exhausted'}), flush=True)
            return False
        event, delay = decision['event'], decision['delay_seconds']
        service = event['service']; assert service in {'generation', 'embedding'}
        cap = variant.transport.LIMITS[service+'_request_seconds']
        if runtime.remaining_seconds() <= delay+cap+2:
            print(json.dumps({'event': 'paused', 'reason': 'insufficient_original_window_for_retry'}), flush=True)
            return False
        body = variant.read(variant.RUN/f"request-{event['sequence']:02}.json")['body']
        assert variant.probe.digest(variant.probe.canonical(body).encode()) == event['request_body_sha256']
        variant.transport.validate_payload(service, body)
        if service == 'generation':
            if state['index_generation_attempts'] >= variant.transport.LIMITS['generation_index_attempts'] or state['generation_input_tokens']+event['input_tokens'] > variant.transport.LIMITS['generation_input_total']:
                print(json.dumps({'event': 'paused', 'reason': 'cumulative_generation_budget'}), flush=True)
                return False
        elif state['embedding_attempts'] >= variant.transport.LIMITS['embedding_attempts'] or Decimal(state['embedding_reserved_tokens']+event['input_tokens'])*Decimal('.13')/1000000 > Decimal('1'):
            print(json.dumps({'event': 'paused', 'reason': 'cumulative_embedding_budget'}), flush=True)
            return False
        successes = verify_successful_cache(runtime)
        print(json.dumps({'event': 'authorized_timeout_backoff', 'sequence': event['sequence'], 'seconds': delay, 'retry_number': decision['retry_number'], 'successful_generation_cache_entries': successes}), flush=True)
        time.sleep(delay)
        if runtime.remaining_seconds() <= cap+2:
            return False
        number = len(state.get('recoveries', []))+1
        snapshot = variant.RUN/f'stopped-{number:02}.json'
        partial = variant.RUN/f'partial-index-at-stop-{number:02}'
        assert not snapshot.exists() and not partial.exists()
        variant.probe.save(snapshot, state)
        if (variant.RUN/'output').exists(): os.rename(variant.RUN/'output', partial)
        state.setdefault('recoveries', []).append({
            'time_utc': variant.transport.now(), 'event': event['sequence'],
            'service': service,
            'reason': ('authorized_policy_checkpoint_before_dispatch' if event.get('request_dispatched') is False else 'timeout_without_complete_response'),
            'explicit_one_time_retry_authorized': True,
            'authorization_scope': POLICY['scope'],
            'authorization_utc': POLICY['user_authorized_utc'],
            'remote_completion_and_cost_unknown': event.get('request_dispatched') is not False,
            'successful_responses_reused': successes,
            'snapshot': snapshot.name,
            'retry_request_body_sha256': event['request_body_sha256'],
            'logical_retry_number': decision['retry_number'], 'backoff_seconds': delay,
        })
        state['verified_resume_ready'] = True
        state['verified_resume_number'] = number
        runtime.save()
        return True
    finally:
        runtime._lock_file.close()


def bind_retry_event():
    """Generation binds before dispatch upstream; also bind embedding attempts."""
    runtime=variant.CodeRuntime(offline=True)
    try:
        state=runtime.ledger;recovery=state['recoveries'][-1]
        matches=[e for e in state['events'] if e['sequence']>recovery['event']
            and e['service']==recovery['service']
            and e['request_body_sha256']==recovery['retry_request_body_sha256']]
        if len(matches)!=1:
            print(json.dumps({'event':'paused','reason':'retry_dispatch_lineage_not_unique'}),flush=True)
            return False
        event=matches[0]
        assert recovery.get('retry_event',event['sequence'])==event['sequence']
        recovery['retry_event']=event['sequence']
        runtime.save()
        return True
    finally:
        runtime._lock_file.close()


def controller(approved):
    assert approved, 'Explicit task-scoped user authorization must precede this entry'
    variant.configure(); variant.check_frozen()
    runtime = variant.CodeRuntime(offline=True)
    try:
        state = runtime.ledger
        assert state['status']=='stopped' and len(state['events'])==107
        assert len(state['recoveries'])==2 and not state.get('verified_resume_ready')
        assert state['started_utc']=='2026-10-13T13:12:59.674100+00:00'
        assert 'window_deadline_utc' not in state
        assert verify_successful_cache(runtime)==104
        assert 'timeout_retry_policy' not in state
        state['timeout_retry_policy'] = POLICY
        runtime.save()
    finally:
        runtime._lock_file.close()
    while prepare_recovery():
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--resume-worker'])
        if not bind_retry_event(): return 1
        state = variant.read(variant.RUN/'summary.json')
        if result.returncode==0 and state['status']=='index_complete': return 0
        if result.returncode==0 or state['status']!='stopped': return 1
    return 1


async def resume_worker():
    variant.configure(); variant.check_frozen()
    state = variant.read(variant.RUN/'summary.json')
    assert state['timeout_retry_policy']==POLICY and state['verified_resume_ready']
    assert state['recoveries'][-1]['event']==state['events'][-1]['sequence']
    assert 'retry_event' not in state['recoveries'][-1]
    return await variant.full_index.index(resume=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--user-approved-task-timeout-retries',action='store_true')
    parser.add_argument('--resume-worker',action='store_true')
    args=parser.parse_args()
    if args.resume_worker:sys.exit(asyncio.run(resume_worker()))
    sys.exit(controller(args.user_approved_task_timeout_retries))
