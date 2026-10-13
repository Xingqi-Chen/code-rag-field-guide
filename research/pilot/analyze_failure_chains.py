"""Recompute post-hoc diagnostics from published evidence; stdlib, no model/network.

This never modifies gold, retrieval, answers, graph tables, or original ledgers.
Extraction witnesses are verbatim selected cached replies, not repaired outputs.
The script checks their hashes against the earlier extraction diagnostics.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'research/pilot/results'
OUT = BASE / 'failure-analysis'


def no_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'http.client.connect'}:
        raise RuntimeError('Offline analysis forbids network access')


sys.addaudithook(no_network)


def read(path):
    return json.loads(path.read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def citations(text):
    values = []
    for group in re.findall(r'Reports\s*\(([^)]*)\)', text):
        values.extend(int(x) for x in re.findall(r'\b\d+\b', group))
    return sorted(set(values))


def lines_with(text, terms):
    return [x for x in text.splitlines() if any(t.lower() in x.lower() for t in terms)]


def build():
    manifest = read(OUT / 'original-manifest.json')
    for path, expected in manifest.items():
        assert sha((ROOT / path).read_bytes()) == expected, path
    entities = read(BASE / 'index/entities.json')
    relations = read(BASE / 'index/relationships.json')
    reports = read(BASE / 'index/community_reports.json')
    units = read(BASE / 'index/text-unit-provenance.json')
    unit_by_id = {u['ms_text_unit_id']: u for u in units}
    diagnostics = {r['sequence']: r for r in read(BASE / 'extraction-format-diagnostics.json')}
    witnesses = read(OUT / 'extraction-witnesses.json')
    original_events = {e['sequence']: e for e in read(BASE / 'execution.json')['events']}
    for unit in witnesses['units']:
        source = unit_by_id[unit['ms_text_unit_id']]
        assert sha(unit['source_text'].encode()) == source['text_sha256']
        assert unit['title'] == source['title']
        for reply in unit['replies']:
            old = diagnostics[reply['sequence']]
            assert sha(reply['content'].encode()) == old['normalized_visible_output_sha256']
            assert reply['operation'] == old['operation']
            assert reply['content'].rstrip().endswith('<|COMPLETE|>') == old['ends_with_expected_complete_marker']
            body = reply['request_body']
            body_hash = sha(json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode())
            assert body_hash == original_events[reply['sequence']]['request_body_sha256']
            prompt = body['input'][0]['content'][0]['text']
            assert unit['source_text'].strip() in prompt

    cases = {}
    gold = {r['id']: r for r in read(ROOT / 'research/pilot/gold.json')}
    for qid in ['Q01', 'Q07', 'Q13']:
        locations = []
        for span in gold[qid]['evidence']:
            containing = [u for u in units if u['path'] == span['path']
                          and u['start_line'] <= span['start_line'] and u['end_line'] >= span['end_line']]
            locations.append({'gold_id': span['id'], 'symbol': span['symbol'],
                'source': f"{span['path']}:L{span['start_line']}-L{span['end_line']}",
                'containing_units': [{'title': u['title'], 'text_unit_id': u['ms_text_unit_id'],
                    'linked_entities': [{'id': e['human_readable_id'], 'title': e['title']}
                                        for e in entities if u['ms_text_unit_id'] in e['text_unit_ids']],
                    'linked_relationship_ids': [r['human_readable_id'] for r in relations
                                               if u['ms_text_unit_id'] in r['text_unit_ids']]}
                    for u in containing]})
        contexts = {}
        for method in ['bm25', 'hybrid', 'ms_basic', 'ms_local']:
            path = BASE / f'budget-supplement/contexts/{qid}-{method}-16000.json'
            d = read(path)
            contexts[method] = {'path': str(path.relative_to(ROOT)),
                'final_context_tokens': d['final_context_tokens'], 'source_text_tokens': d['source_text_tokens'],
                'sources': [s['title'] for s in d['sources']],
                'final_entity_table_ids': [int(r['id']) for t in d['final_tables']
                                          if t['name'] == 'entities' for r in t['rows']]}
        cases[qid] = {'necessary_evidence': locations, 'contexts_16000': contexts}

    propagation = {}
    for qid, terms, entity_ids in [
        ('Q13', ['native string or byte-string keys'], [537]),
        ('G02', ['getstate', 'setstate'], [133, 134])]:
        answer = read(BASE / f'global/answers/{qid}-global.json')
        propagation[qid] = {
            'entities': [e for e in entities if e['human_readable_id'] in entity_ids],
            'reports': [{'id': r['human_readable_id'], 'matching_lines': lines_with(r['full_content'], terms)}
                        for r in reports if lines_with(r['full_content'], terms)
                        and (qid != 'G02' or r['human_readable_id'] in [4, 50, 80])],
            'map_points': [{'batch': batch, 'point': point, **p}
                for batch, points in enumerate(answer['map_points'], 1)
                for point, p in enumerate(points, 1) if lines_with(p['answer'], terms)],
            'reduce_context_lines': lines_with(answer['reduce_context'], terms),
            'final_answer_lines': lines_with(answer['answer'], terms)}
        assert propagation[qid]['map_points'] and propagation[qid]['reduce_context_lines']
        assert propagation[qid]['final_answer_lines']

    g02 = read(BASE / 'global/answers/G02-global.json')
    report_ids = sorted(int(r['id']) for r in read(BASE / 'global/map-contexts.json')['records']['reports'])
    map_ids = citations('\n'.join(p['answer'] for ps in g02['map_points'] for p in ps))
    reduce_ids = citations(g02['reduce_context'])
    final_ids = citations(g02['answer'])
    invalid = {'input_report_ids': report_ids, 'map_citation_ids': map_ids,
        'reduce_context_citation_ids': reduce_ids, 'final_citation_ids': final_ids,
        'final_ids_absent_from_report_input': sorted(set(final_ids) - set(report_ids)),
        'final_ids_absent_from_map_and_reduce': sorted(set(final_ids) - set(map_ids) - set(reduce_ids)),
        'reduce_call_sequence': g02['call_sequences'][-1]}
    assert invalid['final_ids_absent_from_report_input'] == [88]
    assert 88 not in map_ids and 88 not in reduce_ids

    fmt = read(BASE / 'extraction-parser-diagnostics.json')
    affected = fmt['chunks_with_wrong_marker']
    affected_weight = sum(r['relations_with_weight_fallback'] for r in affected)
    format_counts = {'successful_extraction_replies': len(diagnostics),
        'abnormal_endings': sum(not d['ends_with_expected_complete_marker'] for d in diagnostics.values()),
        'affected_chunks': len(affected), 'wrong_marker_variants': fmt['wrong_marker_variants'],
        'weight_fallback_all': fmt['totals_before_merge']['relations_with_weight_fallback'],
        'weight_fallback_affected_chunks': affected_weight,
        'weight_fallback_other_chunks': fmt['totals_before_merge']['relations_with_weight_fallback'] - affected_weight,
        'case_markers': [{'title': u['title'], 'sequences': [r['sequence'] for r in u['replies']],
            'all_endings_expected': all(diagnostics[r['sequence']]['ends_with_expected_complete_marker'] for r in u['replies'])}
            for u in witnesses['units']],
        'note': 'Recounts prior parser diagnostics; not a repaired-parser or retrieval ablation.'}

    budget = read(BASE / 'budget-supplement/budget-analysis.json')['test_summary']
    budget_rows = [{k: row[k] for k in ['method', 'budget', 'context_tokens', 'source_chunks',
        'mean_source_text_tokens', 'mean_budget_utilization', 'coverage80']} for row in budget]
    ledger = read(BASE / 'execution.json')
    events = [e for e in ledger['events'] if e.get('phase') == 'index']
    ops = defaultdict(list)
    for event in events:
        ops[event['operation']].append(event)
    costs = {op: {'physical_requests': len(es), 'request_seconds_sum': round(sum(e['elapsed_seconds'] for e in es), 6),
        'status_counts': dict(Counter(e['status'] for e in es)),
        'known_provider_input_tokens': sum(e.get('usage', {}).get('prompt_tokens', 0) for e in es),
        'unknown_usage_sequences': [e['sequence'] for e in es if not e.get('usage')]}
        for op, es in ops.items()}
    workflows = defaultdict(float)
    for w in ledger['workflow_timing']:
        workflows[w['name']] += w['elapsed_seconds']
    expected_inputs = {
        'entity': {str(e['human_readable_id']): sha((e['title'] + ':' + e['description']).encode()) for e in entities},
        'report': {str(r['human_readable_id']): sha(r['full_content'].encode()) for r in reports},
        'source': {u['title']: u['text_sha256'] for u in units}}
    embedding_parts = defaultdict(lambda: {'batches': 0, 'items': 0, 'provider_input_tokens': 0, 'request_seconds_sum': 0.0})
    event_by_id = {e['sequence']: e for e in events}
    batches = read(OUT / 'embedding-batches.json')['batches']
    assert {b['sequence'] for b in batches} == {e['sequence'] for e in ops['embedding']}
    for batch in batches:
        event = event_by_id[batch['sequence']]
        assert len(batch['items']) == event['items']
        for item in batch['items']:
            assert item['input_sha256'] == expected_inputs[batch['kind']][str(item['id'])]
        part = embedding_parts[batch['kind']]
        part['batches'] += 1
        part['items'] += event['items']
        part['provider_input_tokens'] += event['usage']['prompt_tokens']
        part['request_seconds_sum'] += event['elapsed_seconds']
    for part in embedding_parts.values():
        part['request_seconds_sum'] = round(part['request_seconds_sum'], 6)
    update = read(OUT / 'update-semantics.json')
    upstream_files = read(ROOT / 'research/microsoft-version.json')['source_files']
    assert update['upstream_file_sha256'] == next(x['sha256'] for x in upstream_files if x['path'] == update['upstream_file'])
    update_cases = {c['case']: c for c in update['cases']}
    assert update_cases['same_title_body_edit']['new_titles'] == []
    assert update_cases['new_title']['new_titles'] == ['c.py']
    assert update_cases['delete_b']['deleted_titles'] == ['b.py']
    assert [r['title'] for r in update_cases['delete_b']['merged_by_concat']] == ['a.py', 'b.py']
    assert [r['title'] for r in update_cases['rename_b_to_c']['merged_by_concat']] == ['a.py', 'b.py', 'c.py']
    return {'scope': 'Post-hoc offline diagnosis of existing evidence; selected cases, no rescore, no model calls or graph rebuild. Counts do not estimate causal shares.',
        'preserved_original_files': len(manifest), 'entity_types': dict(Counter(e['type'] for e in entities)),
        'entity_source_coverage': {'linked_units': len({i for e in entities for i in e['text_unit_ids']}), 'total_units': len(units)},
        'source_retrieval_cases': cases, 'summary_propagation': propagation,
        'G02_citation_check': invalid, 'format_diagnostics': format_counts,
        'budget_summary': budget_rows, 'index_requests_by_operation': costs,
        'index_embedding_by_object': dict(embedding_parts),
        'update_probe': {'cases': len(update_cases), 'upstream_file_sha256': update['upstream_file_sha256'], 'scope': update['scope']},
        'index_workflow_seconds_by_stage': dict(workflows),
        'active_index_workflow_seconds': ledger['active_index_workflow_seconds'],
        'stop_gap_seconds': ledger['diagnosed_stop_gap_seconds'],
        'index_calendar_seconds': ledger['index_elapsed_calendar_seconds'],
        'measurement_limits': ['Request time sums are not additional wall-clock stages.',
            'Raw source tokens are counted before CSV serialization; ratios to final context are descriptive, not additive table budgets.',
            'Entity IDs in final tables are displayed rows, not a claim that all vector candidates fit.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build()
    target = OUT / 'analysis.json'
    if args.check:
        assert read(target) == result, 'Analysis is stale'
    else:
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'verified', 'preserved_original_files': result['preserved_original_files'],
        'selected_extraction_units': 4, 'new_generation_calls': 0, 'new_embedding_calls': 0,
        'scope': 'Offline public-evidence reconstruction'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
