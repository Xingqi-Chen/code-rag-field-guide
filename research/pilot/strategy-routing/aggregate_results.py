"""Recompute frozen question-level content and source-coverage comparisons."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

HERE=Path(__file__).resolve().parent;PILOT=HERE.parent;OUT=HERE/'results'
sys.path.insert(0,str(PILOT))
from score_results import score
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
METHODS=('routed_graphrag','bm25','ms_basic','hybrid')

def calculate():
    execution=read(OUT/'execution.json')
    assert execution['status'] in {'complete','complete_with_recorded_failures'} and len(execution['cells'])==92
    rubric=read(HERE/'answer-gold.json');rubrics={x['id']:x for x in rubric['items']}
    mapping={x['anonymous_id']:x for x in read(OUT/'grading-method-map.json')}
    contents={};review_hashes={}
    for file in sorted((HERE/'reviews').glob('content-batch*.json')):
        review=read(file);assert review['rubric_sha256']==sha(HERE/'answer-gold.json')
        pack=OUT/'grading-packs'/file.name.replace('content-batch','blind-content-batch')
        assert sha(pack)==review['blind_pack_sha256']
        packed=read(pack);assert packed['rubric_sha256']==review['rubric_sha256']
        packed_rows={r['anonymous_id']:r for r in packed['rows']}
        assert len(packed_rows)==len(packed['rows'])==len(review['rows'])
        assert set(packed_rows)=={r['anonymous_id'] for r in review['rows']}
        assert all(hashlib.sha256(r['answer'].encode()).hexdigest()==r['answer_sha256'] for r in packed['rows'])
        review_hashes[str(file.relative_to(HERE))]=sha(file)
        for row in review['rows']:
            aid=row['anonymous_id'];assert aid not in contents
            assert all(row[field]==packed_rows[aid][field] for field in ('question_id','answer_sha256','status'))
            question=mapping[aid]['question_id'];assert row['question_id']==question
            assert {x['id'] for x in row['criteria']}=={x['id'] for x in rubrics[question]['criteria']}
            assert len(row['criteria'])==len(rubrics[question]['criteria'])
            assert all(type(x['score']) in (int,float) and x['score'] in {0,.5,1} for x in row['criteria'])
            mean=statistics.mean(x['score'] for x in row['criteria'])
            assert math.isclose(mean,row['content_mean'])
            contents[aid]=row
    assert len(contents)==len(mapping)==92
    by_key={(x['question_id'],x['method']):aid for aid,x in mapping.items()}
    raw_gold={x['id']:x for x in read(PILOT/'gold.json')}
    rows=[]
    for result in execution['cells']:
        qid,method=result['question_id'],result['method'];aid=by_key[qid,method];content=contents[aid]
        assert content['answer_sha256']==result['answer_sha256']
        if result['status']=='failed':assert content['content_mean']==0
        retrieval=score(raw_gold[qid],result['raw_sources_in_http200_contexts']) if qid in raw_gold else None
        rows.append({**{k:v for k,v in result.items() if k!='raw_sources_in_http200_contexts'},
            'anonymous_id':aid,'content_score':content['content_mean'],'content_errors':len(content['errors']),
            'necessary_raw_source_coverage80':retrieval['coverage80'] if retrieval else None,
            'necessary_raw_source_coverage100':retrieval['coverage100'] if retrieval else None,
            'ordered_unique_raw_source_mrr':retrieval['mrr'] if retrieval else None,
            'source_chunks_unique':len(result['raw_sources_in_http200_contexts'])})
    qs=rubric['question_sets']
    cohorts={'main_test16':qs['main_test16_ids'],'main_dev4':qs['main_dev4_ids'],
             'main_all20_descriptive':qs['main20_ids'],'supplement6':qs['supplement6_ids']}
    aggregates=[]
    for cohort,ids in cohorts.items():
        for method in METHODS:
            selected=[r for r in rows if r['method']==method and r['question_id'] in ids];assert len(selected)==len(ids)
            rec=[r['necessary_raw_source_coverage80'] for r in selected if r['necessary_raw_source_coverage80'] is not None]
            completed=[r['content_score'] for r in selected if r['status']=='complete']
            aggregates.append({'cohort':cohort,'method':method,'questions':len(selected),
                'content_score':statistics.mean(r['content_score'] for r in selected),
                'completed_only_content_score_diagnostic':statistics.mean(completed) if completed else None,
                'final_answers':sum(r['status']=='complete' for r in selected),'failed_final_answers':sum(r['status']=='failed' for r in selected),
                'raw_retrieval_scorable_questions':len(rec),'necessary_raw_source_coverage80':statistics.mean(rec) if rec else None,
                'mean_elapsed_seconds':statistics.mean(r['elapsed_seconds'] for r in selected),
                'median_elapsed_seconds':statistics.median(r['elapsed_seconds'] for r in selected),
                'generation_reservations':sum(r['generation_reservations'] for r in selected),
                'common_input_tokens_reserved':sum(r['generation_input_tokens_reserved'] for r in selected),
                'known_provider_input_tokens':sum(r['known_provider_input_tokens'] for r in selected),
                'known_provider_output_tokens':sum(r['known_provider_output_tokens'] for r in selected),
                'provider_usage_unknown_possible_dispatch_events':sum(r['provider_usage_unknown_possible_dispatch_events'] for r in selected),
                'reviewed_non_dispatch_reservations':sum(r['reviewed_non_dispatch_reservations'] for r in selected)})
    paired=[]
    for cohort,ids in cohorts.items():
        lookup={(r['question_id'],r['method']):r for r in rows}
        for baseline in METHODS[1:]:
            differences=[lookup[q,'routed_graphrag']['content_score']-lookup[q,baseline]['content_score'] for q in ids]
            rng=random.Random('20261012:'+cohort+':'+baseline)
            samples=sorted(statistics.mean(rng.choices(differences,k=len(differences))) for _ in range(10000))
            paired.append({'cohort':cohort,'baseline':baseline,'routed_minus_baseline_mean':statistics.mean(differences),
                'wins':sum(d>1e-12 for d in differences),'ties':sum(abs(d)<=1e-12 for d in differences),'losses':sum(d< -1e-12 for d in differences),
                'exploratory_paired_bootstrap_95_percent_interval':[samples[249],samples[9749]]})
    return {'protocol_sha256':sha(HERE/'answer-gold.json'),'execution_sha256':sha(OUT/'execution.json'),
        'content_review_sha256':review_hashes,'rows':rows,'aggregates':aggregates,'paired':paired,
        'failure_counts':dict(Counter(r['failure'] for r in rows if r['status']=='failed')),
        'interpretation':['Answer scores include all planned questions, failed final answers score zero.',
            'Completed-only scores are a selected-subset diagnostic; they never replace the all-planned-question primary denominator.',
            'Supplement overlaps reuse answers and scores; never sum overlapping cohort costs as total spend.',
            'Raw-source union is limited to contexts in HTTP200 generation requests, including traceable subcalls; it does not count graph summaries as raw source.',
            'ordered_unique_raw_source_mrr is only a first-exposure ordering diagnostic across subcalls, not the earlier single-retrieval ranking MRR.',
            'DRIFT/Global use more total context and generations than one-shot baselines; this is a fixed policy comparison, not equal-total-cost causal isolation.',
            'Elapsed time is incremental execution here: original one-shot contexts are reused while DRIFT builds dynamic contexts. It is not an equal-cache production latency benchmark.',
            'Decoder failures are outcomes of this service/adapter configuration; raw SSE is unavailable, so the error category alone cannot establish an algorithm defect or the exact remote output.',
            'Provider-known usage is incomplete where unknown events exist, and differs from common-token budget reservations.',
            'Bootstrap reflects variation across this tiny chosen question set only, not service randomness, future repositories or repeated runs.',
            'Evidence/citation reviews are separate from content scores; no posthoc composite score.']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args();result=calculate()
    path=OUT/'scores.json'
    if args.check:assert read(path)==result
    else:path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result['aggregates'],ensure_ascii=False,indent=2))
