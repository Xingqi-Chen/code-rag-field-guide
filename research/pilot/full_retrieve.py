"""Frozen retrieval evaluation: official context builders, no answer generation.

Retrieval does not read gold. Scoring is a separate offline command. A common
CSV renderer adds exact source locations, counts all tables, and drops only
whole tail entries to meet the shared context budget.
"""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import time

import baselines
import full_runtime as transport
import full_index
import probe_runtime as probe

ROOT, RUN = transport.ROOT, transport.RUN
from result_paths import OUT
METHODS = ['bm25', 'hybrid', 'ms_basic', 'ms_local']
ORDER = ['reports', 'entities', 'relationships', 'claims', 'sources']


def render(tables):
    pieces = []
    for table in tables:
        if not table['rows']:
            continue
        stream = io.StringIO(newline='')
        stream.write(f'-----{table["name"].title()}-----\n')
        writer = csv.writer(stream, delimiter='|', lineterminator='\n')
        writer.writerow(table['columns'])
        writer.writerows([[row.get(c, '') for c in table['columns']] for row in table['rows']])
        pieces.append(stream.getvalue())
    return '\n'.join(pieces)


def budget_tables(tables, limit, count):
    """Longest whole-row prefix; equivalent to deleting tail entries until fit."""
    kept = []
    for table in tables:
        current = {'name': table['name'], 'columns': table['columns'], 'rows': []}
        kept.append(current)
        for row in table['rows']:
            current['rows'].append(row)
            if count(render(kept)) > limit:
                current['rows'].pop()
                return kept
    return kept


def adapt(records, sources):
    tables = []
    for name in ORDER:
        if name not in records or not records[name]:
            continue
        rows = []
        for item in records[name]:
            if item.get('in_context', True) is not True:
                raise transport.Halt('candidate_row_in_actual_context')
            row = {k:v for k,v in item.items() if k != 'in_context'}
            if name == 'sources':
                source = sources[str(row['id'])]
                if row['text'] != source['text']:
                    raise transport.Halt('context_source_text_not_exact')
                row['source'] = source['provenance']['title']
            rows.append(row)
        columns = list(rows[0])
        if name == 'sources': columns = ['id', 'source', 'text']
        tables.append({'name': name, 'columns': columns, 'rows': rows})
    if set(records)-set(ORDER):
        raise transport.Halt('unknown_context_table')
    return tables


def source_mapping(tables, sources):
    result = []
    for table in tables:
        if table['name'] == 'sources':
            for row in table['rows']:
                item = sources[str(row['id'])]
                if row['text'] != item['text']:
                    raise transport.Halt('serialized_source_text_not_exact')
                result.append({'short_id': str(row['id']), 'text_unit_id': item['id'],
                               **item['provenance']})
    return result


def run():
    import pandas as pd
    from graphrag.query.indexer_adapters import (read_indexer_text_units, read_indexer_entities,
        read_indexer_relationships, read_indexer_reports)
    from graphrag.query.structured_search.basic_search.basic_context import BasicSearchContext
    from graphrag.query.structured_search.local_search.mixed_context import LocalSearchMixedContext
    from graphrag.utils.api import get_embedding_store
    from graphrag.tokenizer.get_tokenizer import get_tokenizer
    from graphrag_llm.embedding.embedding_factory import create_embedding

    runtime = transport.Runtime()
    if (OUT/'contexts').exists():
        raise transport.Halt('choose_a_new_results_directory_before_paid_query_embeddings')
    if runtime.ledger['status'] != 'index_complete':
        raise transport.Halt('index_not_complete')
    # This stage has no generation calls. Keep the original full-run deadline.
    runtime.begin('retrieval')
    transport.register(runtime)
    config = full_index.make_config()
    tokenizer = get_tokenizer(encoding_model='o200k_base')
    count = lambda text: len(tokenizer.encode(text))
    embedder = create_embedding(config.embedding_models['default_embedding_model'])
    corpus = full_index.inputs()
    full_index.validate_output(corpus)
    unit_df = pd.read_parquet(RUN/'output/text_units.parquet')
    units = read_indexer_text_units(unit_df)
    input_to_prov = {p['id']: p for p in json.loads((ROOT/'.cache/pilot/provenance.json').read_text())}
    unit_map = {p['text_unit_id']: p for p in json.loads((RUN/'text-unit-map.json').read_text())}
    sources = {t.short_id: {'id': t.id, 'text': t.text,
        'provenance': input_to_prov[unit_map[t.id]['input_id']]} for t in units}
    by_input = {unit_map[t.id]['input_id']: t for t in units}
    ordered = [by_input[r['id']] for r in corpus]  # frozen input order breaks ties
    texts = [t.text for t in ordered]
    text_store = get_embedding_store(config.vector_store, 'text_unit_text')
    vectors = [text_store.search_by_id(t.id).vector for t in ordered]
    if any(v is None or len(v) != 3072 for v in vectors):
        runtime.fail('missing_source_index_vector')
    # The hybrid uses the actual persisted vectors used by Microsoft Basic.
    shared_vector_hash = probe.digest(probe.canonical(vectors).encode())
    entities_df = pd.read_parquet(RUN/'output/entities.parquet')
    rel_df = pd.read_parquet(RUN/'output/relationships.parquet')
    communities_df = pd.read_parquet(RUN/'output/communities.parquet')
    reports_df = pd.read_parquet(RUN/'output/community_reports.parquet')
    levels = [int(x) for x in communities_df['level'].unique() if int(x) <= 2]
    level = max(levels) if levels else None
    basic = BasicSearchContext(text_embedder=embedder, text_unit_embeddings=text_store,
                               text_units=units, tokenizer=tokenizer)
    local = None
    if level is not None:
        local = LocalSearchMixedContext(
            entities=read_indexer_entities(entities_df, communities_df, level),
            entity_text_embeddings=get_embedding_store(config.vector_store, 'entity_description'),
            text_embedder=embedder, text_units=units,
            community_reports=read_indexer_reports(reports_df, communities_df, level),
            relationships=read_indexer_relationships(rel_df), covariates={}, tokenizer=tokenizer)
    questions = json.loads((ROOT/'research/pilot/questions.json').read_text())
    features = json.loads((ROOT/'research/pilot/features.json').read_text())
    all_questions = questions + features
    runtime.workflow = 'shared_query_embeddings'
    started = time.perf_counter()
    query_vectors = runtime.embed([q['query'] for q in all_questions])
    query_embedding_seconds = time.perf_counter()-started
    # Confirm adapter reads exactly the shared cached query vectors, without a
    # source re-embedding or extra query normalization.
    runtime.offline = True
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'provenance.json').write_bytes((ROOT/'.cache/pilot/provenance.json').read_bytes())
    (OUT/'short-id-map.json').write_text(json.dumps([{'short_id':t.short_id,'text_unit_id':t.id,
        'input_id':unit_map[t.id]['input_id']} for t in units],indent=2)+'\n')
    context_dir = OUT/'contexts'
    context_dir.mkdir(exist_ok=False)
    records_out = []
    for q, query_vector in zip(all_questions, query_vectors, strict=True):
        for budget in ([4000, 12000] if q['id'].startswith('Q') else [4000]):
            for method in METHODS:
                runtime.check_deadline()
                t0 = time.perf_counter()
                raw, raw_records, reason = '', {}, None
                if method in {'bm25', 'hybrid'}:
                    ranking = (baselines.bm25(texts, q['query']) if method == 'bm25' else
                               baselines.hybrid(texts, q['query'], vectors, query_vector))
                    raw_records = {'sources': [{'id': ordered[i].short_id, 'text': texts[i]} for i in ranking]}
                else:
                    if method == 'ms_basic':
                        result = basic.build_context(q['query'], k=10, max_context_tokens=budget)
                    elif local is not None:
                        result = local.build_context(q['query'], max_context_tokens=budget,
                            include_entity_names=[], exclude_entity_names=[],
                            text_unit_prop=0.5, community_prop=0.15,
                            top_k_mapped_entities=10, top_k_relationships=10,
                            include_entity_rank=True, include_relationship_weight=True,
                            include_community_rank=False, use_community_summary=False,
                            return_candidate_context=False)
                    else:
                        result = None
                        reason = 'no_community_level_at_or_below_2'
                    if result is not None:
                        raw = result.context_chunks
                        raw_records = {k: json.loads(v.to_json(orient='records'))
                                       for k,v in result.context_records.items()}
                retrieval_seconds = time.perf_counter()-t0
                tables = budget_tables(adapt(raw_records, sources), budget, count)
                final = render(tables)
                if count(final) > budget:
                    runtime.fail('final_context_budget_exceeded')
                mapping = source_mapping(tables, sources)
                public = {'question_id': q['id'], 'method': method, 'budget': budget,
                    'query': q['query'], 'upstream_raw_context': raw if method.startswith('ms_') else None,
                    'upstream_raw_records': raw_records if method.startswith('ms_') else None,
                    'final_context': final, 'final_tables': tables, 'sources': mapping,
                    'raw_context_tokens': count('\n\n'.join(raw) if isinstance(raw,list) else raw) if method.startswith('ms_') else None,
                    'final_context_tokens': count(final), 'source_text_tokens': sum(count(sources[r['short_id']]['text']) for r in mapping),
                    'source_chunks': len(mapping), 'retrieval_compute_seconds': retrieval_seconds,
                    'adaptation_seconds': time.perf_counter()-t0-retrieval_seconds,
                    'empty_reason': reason, 'community_level': level if method == 'ms_local' else None,
                    'dropped_tail_rows': sum(len(v) for v in raw_records.values())-sum(len(t['rows']) for t in tables)}
                filename = f'{q["id"]}-{method}-{budget}.json'
                (context_dir/filename).write_text(json.dumps(public, ensure_ascii=False, indent=2)+'\n')
                records_out.append({k:v for k,v in public.items() if k not in {'query','upstream_raw_context','upstream_raw_records','final_context','final_tables'}} | {'context_file': 'contexts/'+filename})
        print(json.dumps({'event': 'retrieval_question_complete', 'id': q['id']}), flush=True)
    metadata = {'microsoft_version': '3.3.0', 'microsoft_commit': '5faaaf4f5685fa2056fa8c3bf9342cb089f2942f',
        'shared_vector_sha256': shared_vector_hash, 'query_embedding_seconds': query_embedding_seconds,
        'community_level': level, 'index_rows': {name: len(df) for name,df in [
            ('text_units',unit_df),('entities',entities_df),('relationships',rel_df),
            ('communities',communities_df),('community_reports',reports_df)]},
        'records': records_out, 'answer_generation_calls': 0,
        'source_vector_precision': 'The actual persisted Microsoft vector store representation, shared by hybrid and Basic',
        'timing': 'One warm-cache pass; retrieval compute includes query-cache disk read and official vector lookup; shared network query embedding measured separately.'}
    (OUT/'retrieval.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
    runtime.ledger.update(status='retrieval_complete', retrieval_finished_utc=transport.now())
    runtime.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute: run()
