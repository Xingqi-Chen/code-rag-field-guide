"""Offline export, Local retrieval and frozen scoring for code-prompt.

No provider adapter is instantiated. Only existing query vectors are accepted.
Old baselines and scores are read, never regenerated or replaced.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
import code_prompt_experiment as variant
from full_retrieve import adapt, budget_tables, render, source_mapping
from score_results import score

ROOT, RUN, OUT, BASE = variant.ROOT, variant.RUN, variant.OUT, variant.BASE
METHOD = 'ms_local_code_prompt'
BUDGETS = [4000, 8000, 12000, 16000]
read, write, sha = variant.read, variant.write, variant.sha


def no_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'http.client.connect', 'urllib.Request'}:
        raise RuntimeError('Offline code-prompt evaluation forbids networking')


sys.addaudithook(no_network)


def export():
    variant.configure()
    variant.check_frozen()
    import export_run_evidence as exporter
    state = read(RUN/'summary.json')
    partial = state['status']=='stopped'
    stop_number = len(state.get('recoveries',[]))+1
    # Preserve the historical public interruption snapshots across resumptions.
    destination = OUT/('execution-interrupted.json' if stop_number==1 else f'execution-interrupted-{stop_number:02}.json')
    scratch = RUN/f'public-export-stop-{stop_number:02}' if partial else OUT
    exporter.RUN, exporter.OUT = RUN, scratch
    documents = [json.loads(x) for x in (ROOT/'.cache/pilot/input/documents.jsonl').read_text().splitlines()]
    prompts = {variant.PROMPT.read_text().format(entity_types=','.join(variant.TYPES), input_text=d['text'].strip()) for d in documents}
    exporter.main(initial_prompts=prompts)
    path = scratch/('execution-interrupted.json' if partial else 'execution.json')
    public = read(path)
    public.update(variant='code-prompt', prior_cumulative_embedding_tokens=206333,
        cost_notes='Cumulative estimate includes 206333 prior baseline/probe/query tokens. Only new graph embeddings incur new calls; source/query vectors reused. No Fullstar fee estimate. Unknown usage is not zero.',
        evaluation_complete=False)
    if partial:
        assert not destination.exists(), 'Refuse to replace a published interruption snapshot'
        write(destination, public)
        return
    write(path, public)
    # Preserve the original unit provenance including exact Microsoft IDs.
    (OUT/'index/text-unit-provenance.json').write_bytes((BASE/'index/text-unit-provenance.json').read_bytes())
    write(OUT/'imported-embedding-cache.json', read(RUN/'imported-embedding-cache.json'))


def retrieve():
    assert read(RUN/'summary.json')['status']=='index_complete'
    assert not (OUT/'contexts').exists(), 'Refuse to overwrite observed retrieval'
    variant.configure()
    variant.check_frozen()
    ledger_hash = sha(RUN/'summary.json')
    import pandas as pd
    from graphrag.query.indexer_adapters import (read_indexer_entities, read_indexer_reports,
        read_indexer_relationships, read_indexer_text_units)
    from graphrag.query.structured_search.local_search.mixed_context import LocalSearchMixedContext
    from graphrag.tokenizer.get_tokenizer import get_tokenizer
    from graphrag.utils.api import get_embedding_store

    variant.probe.tokenizers()
    config = variant.make_config()
    count = lambda t: len(tokenizer.encode(t))
    tokenizer = get_tokenizer(encoding_model='o200k_base')
    units = read_indexer_text_units(pd.read_parquet(RUN/'output/text_units.parquet'))
    prov = {u['ms_text_unit_id']: u for u in read(BASE/'index/text-unit-provenance.json')}
    assert len(units)==len(prov)==114 and {u.id for u in units}==set(prov)
    sources = {u.short_id: {'id':u.id, 'text':u.text, 'provenance':prov[u.id]} for u in units}
    assert all(hashlib.sha256(u.text.encode()).hexdigest()==prov[u.id]['text_sha256'] for u in units)
    queries = read(variant.HERE/'questions.json')
    for imported in read(RUN/'imported-embedding-cache.json'):
        assert sha(RUN/'embedding-cache'/f"{imported['cache_key']}.json") == imported['cache_sha256']
    vectors = {}
    for q in queries:
        item = read(RUN/'embedding-cache'/f"{variant.transport.embedding_key(q['query'])}.json")
        assert len(item['vector'])==3072 and all(math.isfinite(v) for v in item['vector'])
        vectors[q['query']] = item['vector']
    query_hashes = {q['id']:hashlib.sha256(variant.probe.canonical(vectors[q['query']]).encode()).hexdigest() for q in queries}
    assert query_hashes == read(BASE/'budget-supplement/retrieval.json')['query_vector_sha256']

    class CachedEmbedding:
        def embedding(self, *, input):
            assert len(input)==1 and input[0] in vectors, 'Exact query cache miss'
            return SimpleNamespace(first_embedding=vectors[input[0]])

    dfs = {name:pd.read_parquet(RUN/'output'/f'{name}.parquet') for name in
           ['entities','relationships','communities','community_reports']}
    levels = [int(v) for v in dfs['communities']['level'].unique() if v<=2]
    level = max(levels) if levels else None
    local = None
    if level is not None:
        local = LocalSearchMixedContext(
            entities=read_indexer_entities(dfs['entities'],dfs['communities'],level),
            entity_text_embeddings=get_embedding_store(config.vector_store,'entity_description'),
            text_embedder=CachedEmbedding(),text_units=units,
            community_reports=read_indexer_reports(dfs['community_reports'],dfs['communities'],level),
            relationships=read_indexer_relationships(dfs['relationships']),covariates={},tokenizer=tokenizer)
    store = get_embedding_store(config.vector_store,'text_unit_text')
    ordered_prov = read(BASE/'provenance.json')
    source_vectors = [store.search_by_id(p['ms_text_unit_id']).vector for p in ordered_prov]
    shared_hash = hashlib.sha256(variant.probe.canonical(source_vectors).encode()).hexdigest()
    assert shared_hash == read(BASE/'retrieval.json')['shared_vector_sha256']
    (OUT/'contexts').mkdir()
    (OUT/'provenance.json').write_bytes((BASE/'provenance.json').read_bytes())
    shortmap = [{'short_id':u.short_id,'text_unit_id':u.id,'input_id':prov[u.id]['id']} for u in units]
    write(OUT/'short-id-map.json',shortmap)
    started=time.perf_counter();start_utc=datetime.now(timezone.utc).isoformat();records=[]
    for q in queries:
        for budget in BUDGETS:
            t0=time.perf_counter()
            raw, raw_records = '', {}
            if local is not None:
                result=local.build_context(q['query'],max_context_tokens=budget,
                    include_entity_names=[],exclude_entity_names=[],text_unit_prop=.5,community_prop=.15,
                    top_k_mapped_entities=10,top_k_relationships=10,include_entity_rank=True,
                    include_relationship_weight=True,include_community_rank=False,use_community_summary=False,
                    return_candidate_context=False)
                raw=result.context_chunks
                raw_records={k:json.loads(v.to_json(orient='records')) for k,v in result.context_records.items()}
            compute=time.perf_counter()-t0
            tables=budget_tables(adapt(raw_records,sources),budget,count)
            final=render(tables);mapping=source_mapping(tables,sources)
            record={'variant':'code-prompt','question_id':q['id'],'method':METHOD,'budget':budget,
                'query':q['query'],'upstream_raw_context':raw,'upstream_raw_records':raw_records,
                'final_context':final,'final_tables':tables,'sources':mapping,
                'raw_context_tokens':count('\n\n'.join(raw) if isinstance(raw,list) else raw),
                'final_context_tokens':count(final),'source_text_tokens':sum(count(sources[s['short_id']]['text']) for s in mapping),
                'source_chunks':len(mapping),'retrieval_compute_seconds':compute,
                'adaptation_seconds':time.perf_counter()-t0-compute,
                'empty_reason':None if local is not None else 'no_community_level_at_or_below_2','community_level':level,
                'dropped_tail_rows':sum(len(v) for v in raw_records.values())-sum(len(t['rows']) for t in tables)}
            assert record['final_context_tokens']<=budget
            name=f"{q['id']}-{METHOD}-{budget}.json"
            write(OUT/'contexts'/name,record)
            records.append({k:v for k,v in record.items() if k not in
                {'query','upstream_raw_context','upstream_raw_records','final_context','final_tables'}}|{'context_file':'contexts/'+name})
        print(json.dumps({'event':'offline_local_question_complete','id':q['id']}),flush=True)
    assert ledger_hash==sha(RUN/'summary.json')
    variant.check_frozen()
    write(OUT/'retrieval.json',{'variant':'code-prompt','records':records,'community_level':level,
        'started_utc':start_utc,'elapsed_seconds':time.perf_counter()-started,
        'external_calls':0,'shared_vector_sha256':shared_hash,'paid_ledger_sha256_unchanged':ledger_hash,
        'query_vector_sha256':query_hashes,
        'script_sha256':sha(Path(__file__)),
        'timing':'One warm-cache offline Local pass; not a production speed benchmark.'})


def calculate(tokens=False):
    from verify_results import validate
    for name,digest in read(OUT/'preflight.json')['frozen_files'].items():
        assert sha(ROOT/name)==digest, name
    new=validate(tokens=tokens,out=OUT,budgets=BUDGETS,include_features=False,methods=[METHOD])
    old=read(BASE/'retrieval.json')['records']+read(BASE/'budget-supplement/retrieval.json')['records']
    old=[r for r in old if r['question_id'].startswith('Q')]
    gold={q['id']:q for q in read(variant.HERE/'gold.json')}
    questions={q['id']:q for q in read(variant.HERE/'questions.json')}
    rows=[]
    for r in old+new['records']:
        q=questions[r['question_id']]
        occurrences = [(s['path'],line) for s in r['sources']
                       for line in range(s['start_line'],s['end_line']+1)]
        unique = set(occurrences)
        rows.append({'question_id':q['id'],'method':r['method'],'budget':r['budget'],'split':q['split'],'kind':q['kind'],
            'context_tokens':r['final_context_tokens'],'source_tokens':r['source_text_tokens'],'source_chunks':r['source_chunks'],
            'compute_seconds':r['retrieval_compute_seconds'],
            'duplicate_source_line_fraction':(len(occurrences)-len(unique))/len(occurrences) if occurrences else None,
            **score(gold[q['id']],r['sources'])})
    assert len(rows)==400 and len({(r['question_id'],r['method'],r['budget']) for r in rows})==400
    aggregates=[]
    def average(records, metric):
        values = [r[metric] for r in records if r[metric] is not None]
        return statistics.mean(values) if values else None
    for method in sorted({r['method'] for r in rows}):
        for budget in BUDGETS:
            for split in ['test','dev','all']:
                rs=[r for r in rows if r['method']==method and r['budget']==budget and (split=='all' or r['split']==split)]
                metrics=['coverage80','coverage100','mrr','recall5','recall10','context_tokens','source_tokens','source_chunks',
                         'compute_seconds','duplicate_source_line_fraction']
                aggregates.append({'method':method,'budget':budget,'split':split,'questions':len(rs),
                    'scorable_questions':sum(r['coverage80'] is not None for r in rs),
                    **{m:average(rs,m) for m in metrics}})
    paired=[]
    for budget in BUDGETS:
        for qid,q in questions.items():
            group={r['method']:r for r in rows if r['question_id']==qid and r['budget']==budget}
            if group[METHOD]['coverage80'] is not None:
                paired.append({'question_id':qid,'split':q['split'],'budget':budget,
                    **{f'code_minus_{m}':group[METHOD]['coverage80']-group[m]['coverage80'] for m in ['bm25','hybrid','ms_basic','ms_local']}})
    return {'scope':'Same frozen gold; 80 new code-prompt Local contexts plus 320 untouched baseline contexts. No answer accuracy claim.',
        'rows':rows,'aggregates':aggregates,'paired':paired}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['export','retrieve','score','check'])
    parser.add_argument('--tokens',action='store_true')
    args=parser.parse_args()
    if args.action=='export':export()
    elif args.action=='retrieve':retrieve()
    else:
        result=calculate(args.tokens)
        if args.action=='check':assert result==read(OUT/'scores.json')
        else:write(OUT/'scores.json',result)
        print(json.dumps([r for r in result['aggregates'] if r['method']==METHOD and r['split']=='test'],indent=2))


if __name__=='__main__':main()
