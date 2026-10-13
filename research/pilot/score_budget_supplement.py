"""Validate and score the budget supplement; exact overlap is not semantic noise."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

from result_paths import OUT as BASE, SUPPLEMENT
from score_results import calculate
from verify_results import validate

HERE = Path(__file__).resolve().parent


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--tokens', action='store_true')
    args = parser.parse_args()
    original = validate(tokens=args.tokens)
    extra = validate(tokens=args.tokens, out=SUPPLEMENT, budgets=(8000,16000), include_features=False)
    assert calculate(original) == json.loads((BASE/'scores.json').read_text()), 'original scores changed'
    scores = calculate(extra, budgets=(8000,16000))
    assert extra['shared_vector_sha256'] == original['shared_vector_sha256']
    assert extra['external_model_calls'] == extra['physical_embedding_calls'] == extra['python_network_attempts'] == 0
    for name, expected in extra['original_result_sha256'].items():
        assert hashlib.sha256((BASE/name).read_bytes()).hexdigest() == expected
    questions = {q['id']: q for q in json.loads((HERE/'questions.json').read_text())}
    gold = {q['id']: q for q in json.loads((HERE/'gold.json').read_text())}
    diagnostics = []
    for directory, dataset in [(BASE, original), (SUPPLEMENT, extra)]:
        for row in dataset['records']:
            if row['question_id'] not in questions:
                continue
            context = json.loads((directory/row['context_file']).read_text())
            occurrences = [(s['path'],line) for s in row['sources']
                           for line in range(s['start_line'],s['end_line']+1)]
            unique = set(occurrences)
            evidence = gold[row['question_id']]['evidence']
            gold_lines = {(e['path'],line) for e in evidence
                          for line in range(e['start_line'],e['end_line']+1)}
            counts = {t['name']:len(t['rows']) for t in context['final_tables']}
            diagnostics.append({'question_id':row['question_id'],'method':row['method'],'budget':row['budget'],
                'split':questions[row['question_id']]['split'], 'context_tokens':row['final_context_tokens'],
                'source_text_tokens':row['source_text_tokens'], 'source_chunks':row['source_chunks'],
                'budget_utilization':row['final_context_tokens']/row['budget'],
                'source_line_occurrences':len(occurrences), 'unique_source_lines':len(unique),
                'duplicate_source_line_occurrences':len(occurrences)-len(unique),
                'duplicate_source_line_fraction':(len(occurrences)-len(unique))/len(occurrences) if occurrences else None,
                'duplicate_text_unit_ids':len(row['sources'])-len({s['text_unit_id'] for s in row['sources']}),
                'unjudged_unique_source_lines':len(unique-gold_lines) if evidence else None,
                'unjudged_unique_source_line_fraction':len(unique-gold_lines)/len(unique) if evidence and unique else None,
                'reports':counts.get('reports',0), 'entities':counts.get('entities',0),
                'relationships':counts.get('relationships',0), 'adapter_dropped_tail_rows':row['dropped_tail_rows']})
    summary = []
    all_aggregates = json.loads((BASE/'scores.json').read_text())['aggregates']+scores['aggregates']
    for budget in [4000,8000,12000,16000]:
        for method in ['bm25','hybrid','ms_basic','ms_local']:
            rows = [r for r in diagnostics if r['budget']==budget and r['method']==method and r['split']=='test']
            aggregate = next(a for a in all_aggregates if a['budget']==budget and a['method']==method
                             and a['split']=='test' and a['kind']=='all')
            summary.append({**aggregate,
                'min_context_tokens':min(r['context_tokens'] for r in rows),
                'max_context_tokens':max(r['context_tokens'] for r in rows),
                'mean_source_text_tokens':mean(r['source_text_tokens'] for r in rows),
                'mean_budget_utilization':mean(r['budget_utilization'] for r in rows),
                'mean_duplicate_source_line_fraction':mean(r['duplicate_source_line_fraction'] for r in rows),
                'duplicate_text_unit_ids_total':sum(r['duplicate_text_unit_ids'] for r in rows),
                'mean_unjudged_unique_source_line_fraction':mean(r['unjudged_unique_source_line_fraction'] for r in rows),
                'mean_reports':mean(r['reports'] for r in rows),
                'contexts_with_reports':sum(r['reports']>0 for r in rows),
                'adapter_dropped_tail_rows_total':sum(r['adapter_dropped_tail_rows'] for r in rows)})
    analysis = {'scope':'320 retrieval contexts: original 4000/12000 reused, new 8000/16000. Eight original feature contexts excluded here.',
        'definitions':{
            'coverage':'Frozen necessary source evidence, 80% line coverage; test aggregate excludes Q19, n=15.',
            'length':'Actual final o200k tokens including every table/metadata/source, test n=16. Source tokens counted separately before table serialization.',
            'duplicate':'Mean per-context fraction of repeated (path,line) occurrences in Sources; measures chunk overlap only, not semantic redundancy.',
            'unjudged':'Mean unique source-line fraction outside frozen necessary-evidence union, test n=15. Includes potentially useful context; NOT noise or irrelevance rate.',
            'timing':'New in-memory cached embedding lookups differ from original disk-cache adapter; cross-run timing is not a method speed comparison.'},
        'test_summary':summary, 'per_context_diagnostics':diagnostics}
    for name,value in [('scores.json',scores),('budget-analysis.json',analysis)]:
        if args.check:
            assert json.loads((SUPPLEMENT/name).read_text()) == value, name+' differs from recomputation'
        else:
            (SUPPLEMENT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'verified_new_contexts':len(extra['records']),'original_contexts_reused':len(original['records']),
                      'external_model_calls':0,'summary':summary},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
