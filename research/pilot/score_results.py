"""Recompute frozen evidence coverage from public context provenance, offline."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def coverage(evidence, sources):
    expected = set(range(evidence['start_line'], evidence['end_line']+1))
    found = set()
    for source in sources:
        if source['path'] == evidence['path']:
            found.update(range(source['start_line'], source['end_line']+1))
    return len(expected & found)/len(expected)


def score(gold, sources):
    evidence = gold['evidence']
    if not evidence:
        return {'coverage80': None, 'coverage100': None, 'recall5': None, 'recall10': None,
                'mrr': None, 'evidence': [], 'unanswerable': True}
    hits = [{'id': e['id'], 'line_coverage': coverage(e, sources),
             'hit80': coverage(e, sources) >= .8, 'hit100': coverage(e, sources) == 1}
            for e in evidence]
    mrr = next((1/i for i,s in enumerate(sources,1) if any(coverage(e,[s]) >= .8 for e in evidence)),0)
    return {'coverage80': statistics.mean(x['hit80'] for x in hits),
            'coverage100': statistics.mean(x['hit100'] for x in hits),
            'recall5': statistics.mean(coverage(e,sources[:5]) >= .8 for e in evidence),
            'recall10': statistics.mean(coverage(e,sources[:10]) >= .8 for e in evidence),
            'mrr': mrr, 'evidence': hits, 'unanswerable': False}


def main():
    from verify_results import validate
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',help='Compare recomputation without rewriting saved scores')
    parser.add_argument('--tokens',action='store_true',help='Also recount o200k tokens from actual contexts')
    args=parser.parse_args()
    data = validate(tokens=args.tokens)
    gold = {q['id']:q for q in json.loads((HERE/'gold.json').read_text())}
    feature_gold = {q['id']:q for q in json.loads((HERE/'feature-gold.json').read_text())}
    questions = {q['id']:q for q in json.loads((HERE/'questions.json').read_text())}
    rows, feature_rows = [], []
    for result in data['records']:
        qid = result['question_id']
        if qid in feature_gold:
            feature_rows.append({'feature_id':qid,'method':result['method'],'budget':result['budget'],
                **score(feature_gold[qid],result['sources'])})
            continue
        if qid not in gold: raise ValueError('unknown question')
        rows.append({'question_id':qid, 'method':result['method'], 'budget':result['budget'],
            'split':questions[qid]['split'], 'kind':questions[qid]['kind'],
            'context_tokens':result['final_context_tokens'], 'source_chunks':result['source_chunks'],
            'compute_seconds':result['retrieval_compute_seconds'], **score(gold[qid], result['sources'])})
    metrics = ['coverage80','coverage100','recall5','recall10','mrr','context_tokens','source_chunks','compute_seconds']
    aggregates = []
    for budget in (4000,12000):
        for method in sorted({r['method'] for r in rows}):
            for split in ('all','test','dev'):
                for kind in ('all','locate','trace','impact','negative','unknown'):
                    subset = [r for r in rows if r['budget']==budget and r['method']==method
                              and (split=='all' or r['split']==split) and (kind=='all' or r['kind']==kind)]
                    if not subset: continue
                    aggregate = {'method':method,'budget':budget,'split':split,'kind':kind,
                                 'questions':len(subset),'scorable_questions':sum(r['coverage80'] is not None for r in subset)}
                    for metric in metrics:
                        values = [r[metric] for r in subset if r[metric] is not None]
                        aggregate[metric] = statistics.mean(values) if values else None
                    aggregates.append(aggregate)
    paired = []
    for budget in (4000,12000):
        for baseline in ('bm25','hybrid','ms_basic'):
            for qid in questions:
                pair = {r['method']:r for r in rows if r['budget']==budget and r['question_id']==qid}
                if pair['ms_local']['coverage80'] is not None:
                    paired.append({'question_id':qid,'budget':budget,'baseline':baseline,
                        'local_minus_baseline_coverage80':pair['ms_local']['coverage80']-pair[baseline]['coverage80']})
    result = {'protocol':'Frozen necessary-source-evidence coverage; no generated-answer score',
              'rows':rows,'aggregates':aggregates,'paired_differences':paired,
              'feature_evidence_rows':feature_rows}
    if args.check:
        assert json.loads((HERE/'results/scores.json').read_text())==result, 'saved scores differ from recomputation'
    else:
        (HERE/'results/scores.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([r for r in aggregates if r['budget']==4000 and r['split']=='test' and r['kind']=='all'],indent=2))


if __name__ == '__main__': main()
