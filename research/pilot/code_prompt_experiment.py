"""Isolated code-prompt variant using the existing bounded official runner.

No old completion cache is imported. The upstream algorithms, transport and
scorer are reused; only extraction prompt/types change. No implicit resumption.
"""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import full_runtime as transport
import full_index
import probe_runtime as probe

ROOT = probe.ROOT
HERE = Path(__file__).resolve().parent
RUN = ROOT / '.cache/pilot/code-prompt-20261013'
OLD_RUN = ROOT / '.cache/pilot/full-20261012'
BASE = HERE / 'results'
OUT = BASE / 'code-prompt'
PLAN = HERE / 'code-prompt/plan.json'
PROMPT = HERE / 'code-prompt/extract_graph.txt'
TYPES = ['module', 'class', 'function', 'method', 'test', 'constant', 'external_symbol']
OriginalRuntime = transport.Runtime
original_config = full_index.make_config
original_supervise = probe.supervise


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


class CodeRuntime(OriginalRuntime):
    def complete(self,messages,response_format=None):
        reply=super().complete(messages,response_format)
        if response_format is not None and (RUN/'schema-1027-amendment.json').exists():
            import code_prompt_schema_exception
            return code_prompt_schema_exception.apply(self,messages,response_format,reply)
        return reply

    def remaining_seconds(self):
        if self.ledger.get('wall_deadline_removed') is True:
            return math.inf
        return super().remaining_seconds()

    def begin(self, stage='index', resume=False):
        if self.ledger.get('wall_deadline_removed') is not True:
            return super().begin(stage, resume)
        # Keep the baseline runtime frozen. Its synchronous begin installs the
        # stage timer before any model worker starts. Translate only infinity
        # into a disabled timer, then restore the standard signal API immediately.
        set_timer = transport.signal.setitimer
        def stage_timer(which, seconds, *args):
            disabled = which == transport.signal.ITIMER_REAL and seconds == math.inf
            return set_timer(which, 0 if disabled else seconds, *args)
        transport.signal.setitimer = stage_timer
        try:
            return super().begin(stage, resume)
        finally:
            transport.signal.setitimer = set_timer

    def import_probes(self):
        # Called by parent constructor only for a fresh isolated run.
        old = read(OLD_RUN / 'summary.json')
        published = read(BASE / 'execution.json')
        assert old['embedding_reserved_tokens'] == published['embedding_reserved_tokens'] == 206333
        docs = [json.loads(x) for x in (ROOT / '.cache/pilot/input/documents.jsonl').read_text().splitlines()]
        questions = read(HERE / 'questions.json')
        inputs = [('source', d['id'], d['text']) for d in docs] + [('query', q['id'], q['query']) for q in questions]
        copied = []
        for kind, identity, text in inputs:
            key = transport.embedding_key(text)
            source = OLD_RUN / 'embedding-cache' / (key + '.json')
            value = read(source)
            assert len(value['vector']) == 3072 and all(math.isfinite(v) for v in value['vector'])
            shutil.copyfile(source, RUN / 'embedding-cache' / source.name)
            copied.append({'kind': kind, 'id': identity, 'cache_key': key, 'cache_sha256': sha(source)})
        assert len(copied) == 134 and not list((RUN / 'completion-cache').iterdir())
        self.ledger.update(prior_probe_reserved={'generation_attempts': 0, 'embedding_attempts': 0,
            'generation_input_tokens': 0, 'embedding_input_tokens': 206333, 'embedding_items': 0},
            prior_probe_elapsed_seconds=0, embedding_reserved_tokens=206333,
            prior_cumulative_embedding_tokens=206333,
            imported_successful_probe_cache={'generation': 0, 'embedding_items': len(copied),
                'note': 'Only 114 frozen source and 20 query vectors from the completed baseline; no graph descriptions.'})
        write(RUN / 'imported-embedding-cache.json', copied)
        self.save()


def supervise_variant(argv, *args, **kwargs):
    expected = str(Path(transport.__file__).resolve())
    assert argv[1] == expected and argv[2] == '--worker'
    assert Path(argv[3]).parent.resolve() == RUN.resolve()
    assert Path(argv[4]).parent.resolve() == RUN.resolve()
    return original_supervise([argv[0], str(Path(__file__).resolve()), *argv[2:]], *args, **kwargs)


def make_config():
    config = original_config()
    config.extract_graph.prompt = str(PROMPT)
    config.extract_graph.entity_types = TYPES
    # Record raw per-chunk extraction tables for an evidence-quality audit.
    # This only saves already produced tables, not an algorithm or prompt change.
    config.snapshots.raw_graph = True
    return config


def configure():
    plan = read(PLAN)
    assert plan['changed']['extract_graph.entity_types'] == TYPES
    transport.RUN = full_index.RUN = RUN
    transport.Runtime = CodeRuntime
    amendment_path = RUN/'timeout-amendment-120.json'
    request_seconds = 60
    if amendment_path.exists():
        amendment = read(amendment_path)
        assert amendment['generation_request_seconds']==120
        assert amendment['first_possible_event']==110
        assert amendment['original_deadline_utc']=='2026-10-13T16:12:59.674100+00:00'
        request_seconds = 120
    transport.LIMITS = dict(transport.LIMITS, generation_index_attempts=1200,
        generation_feature_attempts=0, generation_input_total=8000000, wall_seconds=10800,
        generation_request_seconds=request_seconds)
    if (RUN/'summary.json').exists() and read(RUN/'summary.json').get('wall_deadline_removed') is True:
        transport.LIMITS['wall_seconds']=None
    if (RUN/'generation-cap-amendment.json').exists():
        amendment=read(RUN/'generation-cap-amendment.json')
        assert amendment['previous_generation_cap']==1200 and amendment['generation_cap']==1600
        assert amendment['human_approval_utc']=='2026-10-14T00:31:24+00:00'
        transport.LIMITS['generation_index_attempts']=1600
    probe.supervise = supervise_variant
    full_index.make_config = make_config


def prepare():
    assert not RUN.exists() and not OUT.exists(), 'Refuse to replace an existing variant'
    corpus = full_index.inputs()
    config = make_config()
    result = full_index.preflight(config, corpus)
    # Format against only a synthetic fixture here, never questions or gold.
    rendered = PROMPT.read_text().format(entity_types=','.join(TYPES), input_text='def sample(): return 1')
    assert '{input_text}' not in rendered
    runtime = CodeRuntime(create=True, offline=True)
    (RUN / 'input').mkdir()
    shutil.copyfile(ROOT / '.cache/pilot/input/documents.jsonl', RUN / 'input/documents.jsonl')
    config_data = json.loads(json.dumps(config.model_dump(mode='json')).replace(str(RUN), '<RUN>').replace(str(ROOT), '<ROOT>'))
    write(RUN / 'effective-config.json', config_data)
    write(RUN / 'environment.json', {'python': sys.version.split()[0],
        'packages': sorted(f'{d.metadata["Name"]}=={d.version}' for d in importlib.metadata.distributions())})
    frozen = {str(p.relative_to(ROOT)): sha(p) for p in [PLAN, PROMPT, HERE/'questions.json', HERE/'gold.json',
        HERE/'protocol.md', HERE/'global-questions.json', HERE/'global-gold.json', BASE/'execution.json', BASE/'retrieval.json',
        BASE/'scores.json', BASE/'budget-supplement/retrieval.json', BASE/'budget-supplement/scores.json']}
    old_graph = {p.name: sha(p) for p in (OLD_RUN/'output').glob('*.parquet')}
    result.update(variant='code-prompt', frozen_files=frozen, baseline_graph_sha256=old_graph,
        prompt_sha256=sha(PROMPT), changed_fields=['extract_graph.prompt', 'extract_graph.entity_types'],
        additional_output_only=['snapshots.raw_graph'], generation_cache_entries=0,
        reused_source_query_vectors=134, prior_cumulative_embedding_tokens=206333,
        initial_prompt_count=114, glean_count=114, questions_or_gold_in_prompt=False)
    write(RUN / 'preflight.json', result)
    OUT.mkdir()
    write(OUT / 'preflight.json', result)
    write(OUT / 'effective-config.json', config_data)
    write(OUT / 'environment.json', read(RUN/'environment.json'))
    print(json.dumps({'status': 'prepared', 'run': RUN.name, 'inputs': len(corpus),
        'completion_cache_imports': 0, 'embedding_cache_imports': 134,
        'prior_embedding_estimate_usd': 206333 * .13 / 1000000}))


def check_frozen():
    before = read(RUN/'preflight.json')
    for name, digest in before['frozen_files'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in before['baseline_graph_sha256'].items():
        assert sha(OLD_RUN/'output'/name) == digest, name


def worker(request, response):
    if (RUN/'generation-cap-request.json').exists():
        state=read(RUN/'summary.json')
        if state['limits']['generation_index_attempts']==1200:
            seq=len(state['events'])
            assert request.parent.resolve()==response.parent.resolve()==RUN.resolve()
            assert request.name==f'request-{seq:02}.json' and response.name==f'response-{seq:02}.json'
            assert state['status']=='running' and state['supervisor_pid']==os.getppid()
            assert state['events'][-1]['status']=='reserved_before_dispatch'
            assert sha_body(read(request)['body'])==state['events'][-1]['request_body_sha256']
            write(response,{'error_category':'authorized_generation_cap_checkpoint',
                'request_dispatched':False,'policy_checkpoint':True,
                'worker_source_sha256':{Path(module.__file__).name:sha(Path(module.__file__)) for module in [transport,probe]},
                'code_prompt_source_sha256':sha(Path(__file__))})
            return
    # An existing controller cannot retroactively disarm its installed timer.
    # Finish its current request, then pause the next reservation BEFORE sending.
    if (RUN/'deadline-removal-request.json').exists():
        state=read(RUN/'summary.json')
        if not state.get('wall_deadline_removed'):
            seq=len(state['events'])
            assert request.parent.resolve()==response.parent.resolve()==RUN.resolve()
            assert request.name==f'request-{seq:02}.json' and response.name==f'response-{seq:02}.json'
            assert state['status']=='running' and state['supervisor_pid']==os.getppid()
            assert state['events'][-1]['status']=='reserved_before_dispatch'
            assert sha_body(read(request)['body'])==state['events'][-1]['request_body_sha256']
            write(response,{'error_category':'authorized_deadline_policy_checkpoint',
                'request_dispatched':False,'policy_checkpoint':True,
                'worker_source_sha256':{Path(module.__file__).name:sha(Path(module.__file__))
                    for module in [transport,probe]},
                'code_prompt_source_sha256':sha(Path(__file__))})
            return
    if (RUN/'transient-retry-amendment.json').exists():
        import code_prompt_transport
        code_prompt_transport.run(transport,probe,request,response)
    else:
        transport.worker(request, response)
    if response.exists():
        result = read(response)
        result.setdefault('worker_source_sha256', {})['code_prompt_experiment.py'] = sha(Path(__file__))
        if (RUN/'transient-retry-amendment.json').exists():
            result['worker_source_sha256']['code_prompt_transport.py']=sha(HERE/'code_prompt_transport.py')
        write(response, result)


def sha_body(body):
    return probe.digest(probe.canonical(body).encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', nargs='?', choices=['prepare', 'index', 'check-frozen'])
    parser.add_argument('--worker', nargs=2)
    args = parser.parse_args()
    configure()
    if args.worker:
        worker(*map(Path, args.worker))
    elif args.action == 'prepare':
        prepare()
    elif args.action == 'check-frozen':
        check_frozen()
        print('Frozen inputs, protocol and baseline graph unchanged.')
    elif args.action == 'index':
        check_frozen()
        sys.exit(asyncio.run(full_index.index()))
    else:
        parser.error('Choose an action')


if __name__ == '__main__':
    main()
