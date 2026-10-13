"""Add only 8000/16000 retrieval contexts using existing local graph/vectors.

No provider adapter or Runtime instance is created. The embedding interface is
an exact in-memory lookup and raises on a cache miss. Python network operations
are blocked; generation, graph construction and feature editing are absent.
Original 4000/12000 results and the paid execution ledger are never overwritten.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import baselines
import full_index
from full_retrieve import adapt, budget_tables, render, source_mapping, METHODS
import probe_runtime as probe

ROOT = probe.ROOT
RUN = ROOT/'.cache/pilot/full-20261012'
from result_paths import OUT as BASE, SUPPLEMENT as OUT
BUDGETS = [8000, 16000]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def run():
    if OUT.exists():
        raise RuntimeError('supplement already exists; refusing to overwrite observed results')
    blocked = []
    def reject_network(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'http.client.connect', 'urllib.Request'}:
            blocked.append(event)
            raise RuntimeError('network disabled in this offline supplement')
    sys.addaudithook(reject_network)
    started = time.perf_counter()
    started_utc = datetime.now(timezone.utc).isoformat()
    ledger_hash = sha((RUN/'summary.json').read_bytes())
    original_hashes = {name: sha((BASE/name).read_bytes()) for name in
                       ['retrieval.json', 'scores.json', 'execution.json', 'provenance.json', 'short-id-map.json']}
    questions = json.loads((ROOT/'research/pilot/questions.json').read_text())
    query_vectors, query_hashes = {}, {}
    for question in questions:
        text = question['query']
        key = probe.digest(probe.canonical([probe.EMBED, 3072, text]).encode())
        cache = RUN/'embedding-cache'/f'{key}.json'
        vector = json.loads(cache.read_text())['vector']
        assert len(vector) == 3072 and all(math.isfinite(x) for x in vector)
        query_vectors[text] = vector
        query_hashes[question['id']] = sha(probe.canonical(vector).encode())

    class CachedEmbedding:
        logical_calls = 0
        def embedding(self, *, input):
            assert len(input) == 1 and input[0] in query_vectors, 'exact query cache miss'
            self.logical_calls += 1
            return SimpleNamespace(first_embedding=query_vectors[input[0]])

    import pandas as pd
    from graphrag.query.indexer_adapters import (read_indexer_text_units, read_indexer_entities,
        read_indexer_relationships, read_indexer_reports)
    from graphrag.query.structured_search.basic_search.basic_context import BasicSearchContext
    from graphrag.query.structured_search.local_search.mixed_context import LocalSearchMixedContext
    from graphrag.utils.api import get_embedding_store
    from graphrag.tokenizer.get_tokenizer import get_tokenizer

    # Local tokenizer files are hash checked before constructing the official tokenizer.
    probe.tokenizers()
    tokenizer = get_tokenizer(encoding_model='o200k_base')
    count = lambda text: len(tokenizer.encode(text))
    config = full_index.make_config()
    corpus = full_index.inputs()
    full_index.validate_output(corpus)
    unit_df = pd.read_parquet(RUN/'output/text_units.parquet')
    units = read_indexer_text_units(unit_df)
    input_to_prov = {p['id']: p for p in json.loads((BASE/'provenance.json').read_text())}
    unit_map = {p['text_unit_id']: p for p in json.loads((RUN/'text-unit-map.json').read_text())}
    sources = {t.short_id: {'id': t.id, 'text': t.text,
        'provenance': input_to_prov[unit_map[t.id]['input_id']]} for t in units}
    by_input = {unit_map[t.id]['input_id']: t for t in units}
    ordered = [by_input[r['id']] for r in corpus]
    texts = [t.text for t in ordered]
    text_store = get_embedding_store(config.vector_store, 'text_unit_text')
    vectors = [text_store.search_by_id(t.id).vector for t in ordered]
    assert all(v is not None and len(v) == 3072 for v in vectors)
    vector_hash = sha(probe.canonical(vectors).encode())
    original = json.loads((BASE/'retrieval.json').read_text())
    assert vector_hash == original['shared_vector_sha256'], 'source vectors changed'
    dfs = {name: pd.read_parquet(RUN/'output'/f'{name}.parquet') for name in
           ['entities', 'relationships', 'communities', 'community_reports']}
    index_summary = json.loads((BASE/'index-summary.json').read_text())
    for name in dfs:
        assert sha((RUN/'output'/f'{name}.parquet').read_bytes()) == index_summary['tables'][name]['sha256']
    level = max(int(x) for x in dfs['communities']['level'].unique() if int(x) <= 2)
    assert level == original['community_level']
    embedder = CachedEmbedding()
    basic = BasicSearchContext(text_embedder=embedder, text_unit_embeddings=text_store,
                               text_units=units, tokenizer=tokenizer)
    local = LocalSearchMixedContext(
        entities=read_indexer_entities(dfs['entities'], dfs['communities'], level),
        entity_text_embeddings=get_embedding_store(config.vector_store, 'entity_description'),
        text_embedder=embedder, text_units=units,
        community_reports=read_indexer_reports(dfs['community_reports'], dfs['communities'], level),
        relationships=read_indexer_relationships(dfs['relationships']), covariates={}, tokenizer=tokenizer)
    OUT.mkdir()
    (OUT/'contexts').mkdir()
    for name in ['provenance.json', 'short-id-map.json']:
        (OUT/name).write_bytes((BASE/name).read_bytes())
    records = []
    for question in questions:
        query = question['query']
        for budget in BUDGETS:
            for method in METHODS:
                t0 = time.perf_counter()
                raw, raw_records = '', {}
                if method in {'bm25', 'hybrid'}:
                    ranking = (baselines.bm25(texts, query) if method == 'bm25' else
                               baselines.hybrid(texts, query, vectors, query_vectors[query]))
                    raw_records = {'sources': [{'id': ordered[i].short_id, 'text': texts[i]} for i in ranking]}
                else:
                    result = (basic.build_context(query, k=10, max_context_tokens=budget)
                              if method == 'ms_basic' else local.build_context(query,
                        max_context_tokens=budget, include_entity_names=[], exclude_entity_names=[],
                        text_unit_prop=0.5, community_prop=0.15, top_k_mapped_entities=10,
                        top_k_relationships=10, include_entity_rank=True, include_relationship_weight=True,
                        include_community_rank=False, use_community_summary=False, return_candidate_context=False))
                    raw = result.context_chunks
                    raw_records = {k: json.loads(v.to_json(orient='records')) for k,v in result.context_records.items()}
                compute = time.perf_counter()-t0
                tables = budget_tables(adapt(raw_records, sources), budget, count)
                final = render(tables)
                mapping = source_mapping(tables, sources)
                assert count(final) <= budget
                public = {'question_id': question['id'], 'method': method, 'budget': budget,
                    'query': query, 'upstream_raw_context': raw if method.startswith('ms_') else None,
                    'upstream_raw_records': raw_records if method.startswith('ms_') else None,
                    'final_context': final, 'final_tables': tables, 'sources': mapping,
                    'raw_context_tokens': count('\n\n'.join(raw) if isinstance(raw,list) else raw) if method.startswith('ms_') else None,
                    'final_context_tokens': count(final),
                    'source_text_tokens': sum(count(sources[r['short_id']]['text']) for r in mapping),
                    'source_chunks': len(mapping), 'retrieval_compute_seconds': compute,
                    'adaptation_seconds': time.perf_counter()-t0-compute, 'empty_reason': None,
                    'community_level': level if method == 'ms_local' else None,
                    'dropped_tail_rows': sum(len(v) for v in raw_records.values())-sum(len(t['rows']) for t in tables)}
                filename = f'{question["id"]}-{method}-{budget}.json'
                write(OUT/'contexts'/filename, public)
                records.append({k:v for k,v in public.items() if k not in
                    {'query','upstream_raw_context','upstream_raw_records','final_context','final_tables'}} |
                    {'context_file': 'contexts/'+filename})
        print(json.dumps({'event': 'offline_question_complete', 'id': question['id']}), flush=True)
    assert not blocked
    assert ledger_hash == sha((RUN/'summary.json').read_bytes()), 'paid ledger mutated'
    assert all(value == sha((BASE/name).read_bytes()) for name,value in original_hashes.items())
    write(OUT/'retrieval.json', {'microsoft_version': original['microsoft_version'],
        'microsoft_commit': original['microsoft_commit'], 'shared_vector_sha256': vector_hash,
        'community_level': level, 'index_rows': original['index_rows'], 'records': records,
        'answer_generation_calls': 0, 'external_model_calls': 0, 'physical_embedding_calls': 0,
        'offline_cache_lookup_calls': embedder.logical_calls, 'query_vector_sha256': query_hashes,
        'python_network_attempts': len(blocked), 'query_embedding_seconds': 0,
        'started_utc': started_utc, 'finished_utc': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': time.perf_counter()-started,
        'execution_source_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'script_sha256': sha(Path(__file__).read_bytes()), 'original_result_sha256': original_hashes,
        'paid_ledger_sha256_before_and_after': ledger_hash,
        'scope': 'Only new 8000/16000 retrieval contexts. Existing 4000/12000 and all feature outputs unchanged.',
        'timing': 'One warm-cache pass with in-memory query-vector lookup; not directly comparable with prior disk-cache adapter timings.'})
    print(json.dumps({'contexts': len(records), 'external_model_calls': 0,
                      'elapsed_seconds': time.perf_counter()-started}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    if parser.parse_args().execute:
        run()
