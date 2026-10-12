"""Bounded, audited provider adapters for the official GraphRAG pipeline.

Graph algorithms and prompts stay in the pinned upstream package. This module
only supplies its supported LLM interfaces, transport, shared cache and ledger.
Successful compatibility responses are reusable; failures are never cache hits.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import fcntl
import signal
from pathlib import Path
import subprocess
import sys
import threading
import time

import probe_runtime as probe

ROOT = probe.ROOT
RUN = ROOT / '.cache/pilot/full-20261012'
LIMITS = dict(generation_index_attempts=600, generation_feature_attempts=8,
              generation_input_per_request=16000, generation_input_total=4000000,
              generation_output_per_request=2048, generation_request_seconds=60,
              embedding_request_seconds=30, embedding_input_per_item=8000,
              embedding_batch_items=32, embedding_attempts=1000,
              wall_seconds=7200, openai_budget_usd='1.00',
              embedding_usd_per_million='0.13', concurrency=1, retries=0)


class Halt(BaseException):
    """Fail closed through upstream handlers that otherwise swallow Exception."""


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize_messages(messages):
    if isinstance(messages, str):
        messages = [{'role': 'user', 'content': messages}]
    result = []
    for message in messages:
        if (message.get('role') not in {'system', 'user', 'assistant'}
                or not isinstance(message.get('content'), str)
                or any(k not in {'role', 'content', 'refusal'} for k in message)
                or message.get('refusal') is not None):
            raise probe.Stop('unsupported_message')
        result.append({k: message[k] for k in ('role', 'content')})
    if not result:
        raise probe.Stop('empty_messages')
    return result


def completion_key(messages, schema=None):
    return probe.digest(probe.canonical({'endpoint': probe.HOSTS['generation'],
        'body': probe.generation_payload(normalize_messages(messages), schema)}).encode())


def embedding_key(text):
    return probe.digest(probe.canonical([probe.EMBED, 3072, text]).encode())


def validate_completion(reply, enc):
    """Validate a completed reply; report the known upstream cap violation.

    The user accepted that the proxy may ignore requested max_output_tokens.
    Rejecting an already completed reply cannot undo its cost. Keep authentic
    usage and content rather than truncating, concealing, or resending it.
    Transport still limits bytes, time and total physical attempts.
    """
    if reply.get('model') != probe.MODEL:
        raise probe.Stop('response_model_mismatch')
    choices = reply.get('choices', [])
    if len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
        raise probe.Stop('generation_incomplete_or_multiple_choices')
    content = choices[0].get('message', {}).get('content')
    usage = reply.get('usage', {})
    if not isinstance(content, str) or not content.strip():
        raise probe.Stop('empty_generation')
    if any(type(usage.get(k)) is not int or usage[k] < 0
           for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')):
        raise probe.Stop('missing_or_invalid_generation_usage')
    if usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']:
        raise probe.Stop('inconsistent_generation_usage')
    return content, usage


def validate_payload(service, body):
    if service == 'embedding':
        return probe.validate_payload(service, body)
    messages = [{'role': x['role'], 'content': x['content'][0]['text']} for x in body['input']]
    normalize_messages(messages)
    schema = body.get('text', {}).get('format', {}).get('schema')
    expected = probe.generation_payload(messages, schema)
    if expected != body:
        raise probe.Stop('generation_parameters_changed')
    if schema is not None and schema != probe.REPORT_SCHEMA:
        raise probe.Stop('unregistered_schema')


def worker(request, response):
    # Reuse the already tested one-shot HTTP worker with this stage's directory
    # and payload rules. Credentials remain worker-only; no SDK retries exist.
    original_validate = probe.validate_payload
    def checked(service, body):
        if service == 'embedding':
            return original_validate(service, body)
        return validate_payload(service, body)
    probe.RUN = RUN
    probe.LIMITS = LIMITS
    probe.validate_payload = checked
    probe.worker(request, response)


class Runtime:
    def __init__(self, *, create=False, offline=False):
        self.lock = threading.RLock()
        self.oenc, self.eenc = probe.tokenizers()
        self.offline = offline
        self.phase = 'index'
        self.workflow = 'setup'
        self.stopped = False
        if create:
            RUN.mkdir(mode=0o700, parents=False, exist_ok=False)
        self._lock_file = open(RUN/'active.lock', 'a')
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Halt('another_full_stage_process_is_active') from None
        if create:
            (RUN / 'completion-cache').mkdir()
            (RUN / 'embedding-cache').mkdir()
            prior_file=probe.FINISH_RUN / 'summary.json'
            prior = json.loads(prior_file.read_text()) if prior_file.exists() else {
                'reserved':{k:0 for k in ('generation_attempts','embedding_attempts',
                    'generation_input_tokens','embedding_input_tokens','embedding_items')},
                'cumulative_elapsed_seconds':0}
            self.ledger = {'run_id': RUN.name, 'status': 'prepared', 'created_utc': now(),
                'supervisor_pid': os.getpid(), 'limits': LIMITS, 'events': [],
                'logical_completion_calls': 0, 'completion_cache_hits': 0,
                'logical_embedding_calls': 0, 'embedding_cache_items': 0,
                'prior_probe_reserved': prior['reserved'],
                'prior_probe_elapsed_seconds': prior['cumulative_elapsed_seconds'],
                'index_generation_attempts': 0, 'feature_generation_attempts': 0,
                'embedding_attempts': 0, 'generation_input_tokens': 0,
                'embedding_reserved_tokens': prior['reserved']['embedding_input_tokens'],
                'workflows': [], 'source_commit': subprocess.check_output(
                    ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
            self.save()
            self.import_probes()
        else:
            self.ledger = json.loads((RUN / 'summary.json').read_text())
        self.ledger['supervisor_pid'] = os.getpid()

    def save(self):
        probe.save(RUN / 'summary.json', self.ledger)

    def check_deadline(self):
        if 'started_utc' in self.ledger and time.time() >= datetime.fromisoformat(
                self.ledger['started_utc']).timestamp() + LIMITS['wall_seconds']:
            self.fail('full_run_deadline')

    def begin(self, stage='index', resume=False):
        required = {'index': 'prepared', 'retrieval': 'index_complete', 'feature': 'retrieval_complete'}.get(stage)
        marker = f'{stage}-started.lock'
        if resume:
            if stage != 'index' or self.ledger.get('verified_resume_ready') is not True:
                raise Halt('unverified_resume')
            number=self.ledger.get('verified_resume_number',1)
            required, marker = 'stopped', f'index-verified-resume-{number:02}.lock'
        if required is None or self.ledger['status'] != required:
            raise Halt('run_not_ready_for_new_stage')
        fd = os.open(RUN/marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        self.phase = stage
        if resume:self.ledger['verified_resume_ready']=False
        self.ledger.setdefault('started_utc', now())
        self.ledger['status'] = 'running'
        self.ledger.pop('stop_reason', None)
        self.ledger['source_commit'] = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        self.ledger.setdefault('executions', []).append({'stage': stage, 'resume': resume,
            'started_utc': now(), 'source_commit': self.ledger['source_commit'],
            'next_event_sequence': len(self.ledger['events'])+1})
        self.save()
        # A stage-wide timer also interrupts cache/local work. Per-request
        # supervision reaps its worker in finally when this fires.
        remaining = LIMITS['wall_seconds'] - (time.time() - datetime.fromisoformat(self.ledger['started_utc']).timestamp())
        self.check_deadline()
        signal.signal(signal.SIGALRM, lambda *_: self.fail('full_run_deadline'))
        signal.setitimer(signal.ITIMER_REAL, remaining)

    def fail(self, reason):
        if self.stopped:
            raise Halt(self.ledger.get('stop_reason', reason))
        self.stopped = True
        self.ledger.update(status='stopped', stop_reason=reason, stopped_utc=now())
        self.save()
        raise Halt(reason)

    def import_probes(self):
        imported = {'generation': 0, 'embedding_items': 0, 'generation_transport_mismatch_skipped': 0}
        for directory in (probe.KEY_UPDATE_RUN, probe.RESPONSES_RUN, probe.FINISH_RUN):
            for request in sorted(directory.glob('request-*.json')):
                response = request.with_name(request.name.replace('request-', 'response-'))
                if not response.exists():
                    continue
                task, envelope = json.loads(request.read_text()), json.loads(response.read_text())
                if envelope.get('http_status') != 200 or 'response' not in envelope:
                    continue
                body, reply = task['body'], envelope['response']
                origin = f'{directory.name}/{response.name}'
                if task['service'] == 'generation':
                    probe.validate_generation(reply, self.oenc)
                    messages = body.get('messages') or [
                        {'role': m['role'], 'content': m['content'][0]['text']} for m in body['input']]
                    schema = body.get('text', {}).get('format', {}).get('schema')
                    if body != probe.generation_payload(normalize_messages(messages), schema):
                        imported['generation_transport_mismatch_skipped'] += 1
                        continue
                    validate_payload('generation', body)
                    key = completion_key(messages, schema)
                    probe.save(RUN/'completion-cache'/f'{key}.json', {'response': reply, 'origin': origin})
                    imported['generation'] += 1
                else:
                    validate_payload('embedding', body)
                    texts = body['input']
                    tokens = sum(len(self.eenc.encode(t)) for t in texts)
                    probe.validate_embedding(reply, len(texts), tokens)
                    for item in reply['data']:
                        key = embedding_key(texts[item['index']])
                        probe.save(RUN/'embedding-cache'/f'{key}.json',
                                   {'vector': item['embedding'], 'origin': origin})
                        imported['embedding_items'] += 1
        self.ledger['imported_successful_probe_cache'] = imported
        self.save()

    def request(self, service, body, token_counts):
        with self.lock:
            if self.offline:
                raise Halt('offline_cache_miss')
            if self.stopped or self.ledger['status'] != 'running':
                self.fail('run_not_running')
            started = datetime.fromisoformat(self.ledger['started_utc']).timestamp()
            remaining = LIMITS['wall_seconds'] - (time.time() - started)
            if remaining <= 0:
                self.fail('full_run_deadline')
            validate_payload(service, body)
            if service == 'generation':
                key = self.phase + '_generation_attempts'
                if self.ledger[key] >= LIMITS['generation_' + self.phase + '_attempts']:
                    self.fail('generation_attempt_limit')
                if (len(token_counts) != 1 or not 0 < token_counts[0] <= LIMITS['generation_input_per_request']
                        or self.ledger['generation_input_tokens'] + sum(token_counts) > LIMITS['generation_input_total']):
                    self.fail('generation_input_limit')
                self.ledger[key] += 1
                self.ledger['generation_input_tokens'] += sum(token_counts)
            else:
                if (not token_counts or len(token_counts) > 32
                        or any(not 0 < n <= 8000 for n in token_counts)
                        or self.ledger['embedding_attempts'] >= LIMITS['embedding_attempts']):
                    self.fail('embedding_input_or_attempt_limit')
                total = self.ledger['embedding_reserved_tokens'] + sum(token_counts)
                if Decimal(total)*Decimal('0.13')/1000000 > Decimal('1.00'):
                    self.fail('embedding_dollar_limit')
                self.ledger['embedding_attempts'] += 1
                self.ledger['embedding_reserved_tokens'] = total
            seq = len(self.ledger['events']) + 1
            event = {'sequence': seq, 'service': service, 'phase': self.phase,
                     'workflow': self.workflow, 'input_tokens': sum(token_counts),
                     'items': len(token_counts), 'status': 'reserved_before_dispatch',
                     'request_body_sha256': probe.digest(probe.canonical(body).encode()), 'started_utc': now(),
                     'source_commit': self.ledger['source_commit']}
            self.ledger['events'].append(event)
            request, response = RUN/f'request-{seq:02}.json', RUN/f'response-{seq:02}.json'
            probe.save(request, {'service': service, 'body': body})
            self.save()
            outcome = probe.supervise([sys.executable, str(Path(__file__).resolve()),
                '--worker', str(request), str(response)], LIMITS[service+'_request_seconds']+2,
                time.monotonic()+remaining)
            event.update(outcome)
            if not response.exists():
                event['status'] = 'uncertain_no_response'
                self.fail('uncertain_request_no_automatic_replay')
            envelope = json.loads(response.read_text())
            event.update({k: v for k,v in envelope.items() if k != 'response'})
            if envelope.get('http_status') != 200:
                event['status'] = 'failed'
                self.fail(envelope.get('error_category', 'http_error'))
            reply = envelope['response']
            try:
                if service == 'generation':
                    content, usage = validate_completion(reply, self.oenc)
                    event['visible_output_common_tokens'] = len(self.oenc.encode(content))
                    event['requested_output_limit_exceeded'] = (
                        usage['completion_tokens'] > 2048 or event['visible_output_common_tokens'] > 2048)
                else:
                    usage = probe.validate_embedding(reply, len(token_counts), sum(token_counts))
            except probe.Stop as error:
                event['status'] = 'invalid_response'
                event['validation_reason'] = str(error)
                self.fail(str(error))
            event.update(status='validated', usage=usage)
            self.save()
            print(json.dumps({'event': 'request_validated', 'sequence': seq, 'service': service,
                'workflow': self.workflow, 'elapsed_seconds': event['elapsed_seconds'],
                'index_attempts': self.ledger['index_generation_attempts'],
                'embedding_reserved_usd': str(Decimal(self.ledger['embedding_reserved_tokens'])*Decimal('.13')/1000000)}), flush=True)
            return reply, f'{RUN.name}/{response.name}'

    def complete(self, messages, response_format=None):
        with self.lock:
            self.check_deadline()
            self.ledger['logical_completion_calls'] += 1
            messages = normalize_messages(messages)
            schema = probe.REPORT_SCHEMA if response_format is not None else None
            key = completion_key(messages, schema)
            cache = RUN/'completion-cache'/f'{key}.json'
            if cache.exists():
                self.ledger['completion_cache_hits'] += 1
                reply = json.loads(cache.read_text())['response']
                self.save()
            else:
                body = probe.generation_payload(messages, schema)
                tokens = sum(len(self.oenc.encode(m['content'])) for m in messages)
                reply, origin = self.request('generation', body, [tokens])
                probe.save(cache, {'response': reply, 'origin': origin})
            validate_completion(reply, self.oenc)
            return reply

    def embed(self, texts):
        with self.lock:
            self.check_deadline()
            self.ledger['logical_embedding_calls'] += 1
            missing = list(dict.fromkeys(t for t in texts if not (RUN/'embedding-cache'/f'{embedding_key(t)}.json').exists()))
            self.ledger['embedding_cache_items'] += len(texts) - sum(t in missing for t in texts)
            self.save()
            for start in range(0, len(missing), 32):
                batch = missing[start:start+32]
                counts = [len(self.eenc.encode(t)) for t in batch]
                reply, origin = self.request('embedding', {'model': probe.EMBED, 'input': batch,
                    'dimensions': 3072, 'encoding_format': 'float'}, counts)
                for item in reply['data']:
                    probe.save(RUN/'embedding-cache'/f'{embedding_key(batch[item["index"]])}.json',
                        {'vector': item['embedding'], 'origin': origin})
            return [json.loads((RUN/'embedding-cache'/f'{embedding_key(t)}.json').read_text())['vector'] for t in texts]


def register(runtime):
    from graphrag_llm.completion.completion import LLMCompletion
    from graphrag_llm.embedding.embedding import LLMEmbedding
    from graphrag_llm.completion.completion_factory import register_completion
    from graphrag_llm.embedding.embedding_factory import register_embedding
    from graphrag_llm.tokenizer.tiktoken_tokenizer import TiktokenTokenizer
    from graphrag_llm.types import LLMCompletionResponse, LLMEmbeddingResponse
    from graphrag_llm.utils import structure_completion_response

    class Adapter:
        def __init__(self, *, metrics_store, **kwargs):
            self._metrics_store = metrics_store
            self._tokenizer = TiktokenTokenizer(encoding_name='o200k_base')
        @property
        def tokenizer(self): return self._tokenizer
        @property
        def metrics_store(self): return self._metrics_store

    class Completion(Adapter, LLMCompletion):
        def completion(self, **kwargs):
            try:
                return self._completion(**kwargs)
            except Exception:
                runtime.fail('completion_adapter_error_redacted')
        def _completion(self, **kwargs):
            if set(kwargs) - {'messages', 'response_format'}:
                raise Halt('unexpected_completion_arguments')
            reply = runtime.complete(kwargs['messages'], kwargs.get('response_format'))
            result = LLMCompletionResponse(id='cached-or-audited', created=0,
                object='chat.completion', model=reply['model'], usage=reply['usage'],
                choices=[{'index': 0, 'finish_reason': 'stop',
                    'message': {'role': 'assistant', 'content': reply['choices'][0]['message']['content']}}])
            if kwargs.get('response_format') is not None:
                try:
                    result.formatted_response = structure_completion_response(result.content, kwargs['response_format'])
                except Exception:
                    runtime.fail('community_report_schema_invalid')
            return result
        async def completion_async(self, **kwargs): return self.completion(**kwargs)

    class Embedding(Adapter, LLMEmbedding):
        def embedding(self, **kwargs):
            try:
                return self._embedding(**kwargs)
            except Exception:
                runtime.fail('embedding_adapter_error_redacted')
        def _embedding(self, **kwargs):
            if set(kwargs) - {'input'}:
                raise Halt('unexpected_embedding_arguments')
            vectors = runtime.embed(kwargs['input'])
            # Transport usage belongs to the ledger. Zero here means no additional
            # billing attributed by this wrapper, not zero provider usage.
            return LLMEmbeddingResponse(object='list', model=probe.EMBED,
                data=[{'index': i, 'object': 'embedding', 'embedding': v} for i,v in enumerate(vectors)],
                usage={'prompt_tokens': 0, 'total_tokens': 0})
        async def embedding_async(self, **kwargs): return self.embedding(**kwargs)

    register_completion('bounded_responses', Completion)
    register_embedding('bounded_openai_embedding', Embedding)
    return Completion, Embedding


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', nargs=2)
    args = parser.parse_args()
    if args.worker:
        worker(*map(Path, args.worker))
