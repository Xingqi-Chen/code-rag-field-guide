"""Run the pinned Microsoft Standard pipeline; never scores or loads gold."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import time

import full_runtime as transport
from full_runtime import ROOT, RUN, Halt
import probe_runtime as probe

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['PYTHONHASHSEED'] = '20261012'


def make_config():
    import yaml
    from graphrag.config.models.graph_rag_config import GraphRagConfig
    data = yaml.safe_load((ROOT/'research/pilot/ms-settings.selected.yaml').read_text())
    data['completion_models'] = {'default_completion_model': {
        'type': 'bounded_responses', 'model_provider': 'openai', 'model': probe.MODEL,
        'metrics': None}}
    data['embedding_models'] = {'default_embedding_model': {
        'type': 'bounded_openai_embedding', 'model_provider': 'openai', 'model': probe.EMBED,
        'metrics': None}}
    for section in ('input_storage', 'output_storage', 'update_output_storage', 'reporting'):
        data[section]['base_dir'] = str(RUN/data[section]['base_dir'])
    data['cache']['storage']['base_dir'] = str(RUN/'upstream-cache')
    data['vector_store']['db_uri'] = str(RUN/'output/lancedb')
    data['embed_text']['batch_size'] = 32
    data['cluster_graph']['seed'] = 20261012
    return GraphRagConfig(**data)


def inputs():
    subprocess.run([sys.executable, str(ROOT/'research/pilot/verify.py'), '--source'],
                   check=True, stdout=subprocess.DEVNULL)
    rows = [json.loads(s) for s in (ROOT/'.cache/pilot/input/documents.jsonl').read_text().splitlines()]
    if len(rows) != 114 or len({r['id'] for r in rows}) != 114:
        raise Halt('input_count_or_id_mismatch')
    return rows


def preflight(config, rows):
    from graphrag_chunking.chunker_factory import create_chunker
    from graphrag.tokenizer.get_tokenizer import get_tokenizer
    from graphrag.index.workflows.create_base_text_units import chunk_document
    from graphrag.index.utils.hashing import gen_sha512_hash
    tok = get_tokenizer(encoding_model='o200k_base')
    chunker = create_chunker(config.chunking, tok.encode, tok.decode)
    ids = []
    for row in rows:
        output = chunk_document(row, chunker)
        if output != [row['text']]:
            raise Halt('upstream_rechunk_changed_text')
        ids.append(gen_sha512_hash(row, ['text']))
    if len(set(ids)) != len(ids):
        raise Halt('text_unit_id_collision')
    return {'inputs': len(rows), 'exact_one_to_one_rechunk': True, 'unique_text_unit_ids': len(set(ids))}


def validate_output(rows):
    import pandas as pd
    df = pd.read_parquet(RUN/'output/text_units.parquet')
    source = {r['id']: r for r in rows}
    if len(df) != len(rows) or df.id.nunique() != len(rows):
        raise Halt('actual_text_units_count_or_id_mismatch')
    mapping = []
    for row in df.to_dict('records'):
        document_id = row.get('document_id')
        if document_id is None:
            document_ids = list(row['document_ids'])
            if len(document_ids) != 1:
                raise Halt('multiple_document_ids')
            document_id = document_ids[0]
        original = source[document_id]
        if row['text'] != original['text']:
            raise Halt('actual_text_unit_text_changed')
        mapping.append({'input_id': document_id, 'text_unit_id': row['id'],
                        'title': original['title'], 'sha256': hashlib.sha256(row['text'].encode()).hexdigest()})
    if len({r['input_id'] for r in mapping}) != 114:
        raise Halt('actual_document_mapping_not_bijective')
    probe.save(RUN/'text-unit-map.json', mapping)
    return mapping


def prepare():
    runtime = transport.Runtime(create=True, offline=True)
    config, rows = make_config(), inputs()
    result = preflight(config, rows)
    (RUN/'input').mkdir()
    shutil.copyfile(ROOT/'.cache/pilot/input/documents.jsonl', RUN/'input/documents.jsonl')
    config_public = config.model_dump(mode='json')
    config_public = json.loads(json.dumps(config_public).replace(str(RUN), '<RUN>'))
    probe.save(RUN/'effective-config.json', config_public)
    versions = sorted(f'{d.metadata["Name"]}=={d.version}' for d in importlib.metadata.distributions())
    probe.save(RUN/'environment.json', {'python': sys.version.split()[0], 'packages': versions})
    # Check exact cache identity; never normalize whitespace to force reuse.
    prompts = probe.prompt_values()
    reusable = sum((RUN/'completion-cache'/(transport.completion_key([{'role': 'user',
        'content': prompts['GRAPH_EXTRACTION_PROMPT'].format(entity_types='organization,person,geo,event',
                                                           input_text=r['text'].strip())}])+'.json')).exists() for r in rows)
    result['exact_upstream_initial_prompt_cache_hits_available'] = reusable
    probe.save(RUN/'preflight.json', result)
    print(json.dumps(result))


async def index(resume=False):
    import importlib
    from graphrag.api.index import build_index
    from graphrag.callbacks.noop_workflow_callbacks import NoopWorkflowCallbacks
    from graphrag.index.typing.stats import WorkflowMetrics
    # The user explicitly disabled resource monitoring. Replace only upstream
    # instrumentation, not any indexing algorithm. Memory fields are UNMEASURED
    # placeholders and must never be reported as measured zero consumption.
    class TimingOnly:
        def __enter__(self):
            self.started = time.monotonic()
            return self
        def __exit__(self, *args):
            self.elapsed = time.monotonic() - self.started
        @property
        def metrics(self):
            return WorkflowMetrics(self.elapsed, 0, 0, 0)
    importlib.import_module('graphrag.index.run.run_pipeline').WorkflowProfiler = TimingOnly
    runtime = transport.Runtime()
    transport.register(runtime)
    config, rows = make_config(), inputs()
    preflight(config, rows)

    class Callbacks(NoopWorkflowCallbacks):
        def workflow_start(self, name, instance):
            runtime.check_deadline()
            runtime.workflow = name
            runtime.ledger['workflows'].append({'name': name, 'status': 'running', 'started_utc': transport.now()})
            runtime.save()
            print(json.dumps({'event': 'workflow_start', 'name': name}), flush=True)
        def workflow_end(self, name, instance):
            runtime.check_deadline()
            if name in {'create_base_text_units', 'create_final_text_units'}:
                validate_output(rows)
            runtime.ledger['workflows'][-1].update(status='complete', finished_utc=transport.now())
            runtime.save()
            print(json.dumps({'event': 'workflow_complete', 'name': name}), flush=True)
        def pipeline_error(self, error):
            runtime.fail('upstream_pipeline_error_' + type(error).__name__)

    runtime.begin(resume=resume)
    t = time.monotonic()
    try:
        outputs = await build_index(config, method='standard', callbacks=[Callbacks()])
        if any(r.error is not None for r in outputs) or len(outputs) != len(config.workflows):
            runtime.fail('upstream_pipeline_incomplete')
        validate_output(rows)
        runtime.check_deadline()
        runtime.ledger.update(status='index_complete', index_elapsed_seconds=round(time.monotonic()-t,3),
                              index_finished_utc=transport.now())
        runtime.save()
        print(json.dumps({'event': 'index_complete', 'elapsed_seconds': runtime.ledger['index_elapsed_seconds']}), flush=True)
    except Halt as error:
        if runtime.ledger['status'] != 'stopped':
            runtime.ledger.update(status='stopped', stop_reason=str(error), stopped_utc=transport.now())
            runtime.save()
        print(json.dumps({'event': 'stopped', 'reason': str(error)}), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'index', 'resume-verified-index'])
    args = parser.parse_args()
    if args.action == 'prepare': prepare()
    else: sys.exit(asyncio.run(index(resume=args.action=='resume-verified-index')))
