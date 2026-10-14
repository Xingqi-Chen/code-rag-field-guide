"""Overlay only six separately graded retry answers; original scores immutable."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'strategy-routing';OUT=HERE/'results'
sys.path.insert(0,str(HERE.parent))
from score_results import score
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
METHODS=('routed_graphrag','bm25','ms_basic','hybrid')
RETRY_QIDS={'Q08','Q10','Q11','Q14','Q16','Q18'}

def validate_content_inputs():
    """Bind complete, unique judgments to the actual six exported answers."""
    original=read(OLD/'results/scores.json');execution=read(OUT/'execution.json');rubric=read(OLD/'answer-gold.json')
    review=read(HERE/'content-review.json');pack=read(OUT/'blind-content-pack.json')
    assert execution['status'] in {'complete','complete_with_recorded_failures'}
    assert execution['original_execution_sha256']==sha(OLD/'results/execution.json')
    assert not review.get('pending') and not any(x in str(review.get('status','')).lower() for x in ('in_progress','pending','partial'))
    assert review['rubric_sha256']==sha(OLD/'answer-gold.json') and review['blind_pack_sha256']==sha(OUT/'blind-content-pack.json')
    assert pack['rubric_sha256']==review['rubric_sha256']
    expected={x['anonymous_id']:x for x in pack['rows']};gold={q['id']:q for q in rubric['items']};grades={}
    assert len(expected)==len(pack['rows'])==len(review['rows'])==6
    assert {r['anonymous_id'] for r in review['rows']}==set(expected)
    assert {r['question_id'] for r in pack['rows']}==RETRY_QIDS
    retries={r['question_id']:r for r in execution['cells']}
    assert len(retries)==len(execution['cells'])==6 and set(retries)==RETRY_QIDS
    questions={q['id']:q for q in read(OLD/'queries.json')}
    for p in pack['rows']:
        result=retries[p['question_id']]
        assert result['method']=='routed_graphrag' and result['route']=='drift'
        assert result['status'] in {'complete','failed'}
        assert p['status']==('completed' if result['status']=='complete' else 'failed')
        assert p['query']==questions[p['question_id']]['query']
        assert isinstance(p['answer'],str) and hashlib.sha256(p['answer'].encode()).hexdigest()==p['answer_sha256']==result['answer_sha256']
        cell=read(OUT/result['cell_file'])
        assert (cell['qid'],cell['method'],cell['route'],cell['status'])==(p['question_id'],'routed_graphrag','drift',result['status'])
        assert (cell.get('answer') or '')==p['answer']
        if p['status']=='failed':assert not p['answer']
    for row in review['rows']:
        p=expected[row['anonymous_id']];qid=p['question_id'];assert qid not in grades
        for key in ('question_id','answer_sha256','status'):assert row[key]==p[key]
        assert {c['id'] for c in row['criteria']}=={c['id'] for c in gold[qid]['criteria']} and len(row['criteria'])==len(gold[qid]['criteria'])
        assert all(type(c['score']) in (int,float) and c['score'] in (0,.5,1) for c in row['criteria'])
        assert type(row['content_mean']) in (int,float)
        assert row['content_mean']==statistics.mean(c['score'] for c in row['criteria'])
        assert isinstance(row['errors'],list)
        for c in row['criteria']:
            if 'answer_quote' in c:assert isinstance(c['answer_quote'],str) and c['answer_quote'] in p['answer']
        if p['status']=='failed':assert row['content_mean']==0
        grades[qid]=row
    assert set(grades)==RETRY_QIDS
    assert len(original['rows'])==92 and len({(r['question_id'],r['method']) for r in original['rows']})==92
    assert all(r['status']=='failed' for r in original['rows'] if r['method']=='routed_graphrag' and r['question_id'] in RETRY_QIDS)
    return original,execution,rubric,review,pack,grades

def calculate():
    original,execution,rubric,review,pack,grades=validate_content_inputs()
    retries={c['question_id']:c for c in execution['cells']};rawgold={q['id']:q for q in read(HERE.parent/'gold.json')}
    rows=copy.deepcopy(original['rows'])
    for r in rows:
        qid=r['question_id']
        if r['method']!='routed_graphrag' or qid not in grades:continue
        x=retries[qid];g=grades[qid];assert r['status']=='failed' and g['answer_sha256']==x['answer_sha256']
        rec=score(rawgold[qid],x['raw_sources_in_http200_contexts']) if qid in rawgold else None
        r.update(original_status=r['status'],original_content_score=r['content_score'],retry_result_file='research/pilot/strategy-routing-retry/results/'+x['cell_file'],
            status=x['status'],failure=x['failure'],answer_sha256=x['answer_sha256'],anonymous_id=g['anonymous_id'],content_score=g['content_mean'],content_errors=len(g['errors']),
            necessary_raw_source_coverage80=rec['coverage80'] if rec else None,necessary_raw_source_coverage100=rec['coverage100'] if rec else None,
            ordered_unique_raw_source_mrr=rec['mrr'] if rec else None,source_chunks_unique=len(x['raw_sources_in_http200_contexts']),
            generation_input_tokens_reserved=x['generation_input_tokens_reserved_including_old_failed_attempts'],
            generation_reservations=r['generation_reservations']+x['new_generation_reservations'],elapsed_seconds=r['elapsed_seconds']+x['elapsed_seconds_new'],
            known_provider_input_tokens=r['known_provider_input_tokens']+x['known_provider_input_tokens_new'],
            known_provider_output_tokens=r['known_provider_output_tokens']+x['known_provider_output_tokens_new'],
            provider_usage_known_events=r['provider_usage_known_events']+x['provider_usage_known_new_generation_events'],
            cache_uses_without_new_physical_fee=r['cache_uses_without_new_physical_fee']+x['new_run_cache_read_operations'],
            provider_usage_unknown_possible_dispatch_events=r['provider_usage_unknown_possible_dispatch_events']+x['provider_usage_unknown_new_generation_events'])
    original_by_key={(r['question_id'],r['method']):r for r in original['rows']}
    assert sum(r==original_by_key[r['question_id'],r['method']] for r in rows)==86
    qs=rubric['question_sets'];cohorts={'main_test16':qs['main_test16_ids'],'main_dev4':qs['main_dev4_ids'],'main_all20_descriptive':qs['main20_ids'],'supplement6':qs['supplement6_ids']}
    aggregates=[];paired=[]
    for cohort,ids in cohorts.items():
        for method in METHODS:
            selected=[r for r in rows if r['method']==method and r['question_id'] in ids];assert len(selected)==len(ids)
            rec=[r['necessary_raw_source_coverage80'] for r in selected if r['necessary_raw_source_coverage80'] is not None]
            aggregates.append({'cohort':cohort,'method':method,'questions':len(selected),'content_score':statistics.mean(r['content_score'] for r in selected),
                'final_answers':sum(r['status']=='complete' for r in selected),'failed_final_answers':sum(r['status']=='failed' for r in selected),
                'raw_retrieval_scorable_questions':len(rec),
                'necessary_raw_source_coverage80':statistics.mean(rec) if rec else None,
                'generation_reservations_including_old_attempts':sum(r['generation_reservations'] for r in selected),
                'common_input_tokens_including_old_attempts':sum(r['generation_input_tokens_reserved'] for r in selected)})
        lookup={(r['question_id'],r['method']):r for r in rows}
        for method in METHODS[1:]:
            ds=[lookup[q,'routed_graphrag']['content_score']-lookup[q,method]['content_score'] for q in ids]
            rng=random.Random('20261012:'+cohort+':'+method);samples=sorted(statistics.mean(rng.choices(ds,k=len(ds))) for _ in range(10000))
            paired.append({'cohort':cohort,'baseline':method,'routed_minus_baseline_mean':statistics.mean(ds),'wins':sum(d>1e-12 for d in ds),'ties':sum(abs(d)<=1e-12 for d in ds),'losses':sum(d< -1e-12 for d in ds),'exploratory_paired_bootstrap_95_percent_interval':[samples[249],samples[9749]]})
    return {'original_scores_sha256':sha(OLD/'results/scores.json'),'retry_execution_sha256':sha(OUT/'execution.json'),'rubric_sha256':sha(OLD/'answer-gold.json'),'content_review_sha256':sha(HERE/'content-review.json'),
        'rows':rows,'aggregates':aggregates,'paired':paired,'interpretation':['Only six original failed routed-GraphRAG cells replaced; other 86 cells and scores are exact reuses.','Original results retained separately; this is post-failure conditional retry, not a new independent test.','Costs and elapsed times include old failed attempts plus new work, and are not an equal-cache latency benchmark.','Unknown usage of six old decoder failures remains unknown.','Model randomness and missing old raw replies prevent attribution of all changes to the decoder repair.','Same frozen content rubric; evidence/citation scores remain separate.']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();x=calculate()
    if a.check:assert read(OUT/'scores.json')==x
    else:(OUT/'scores.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(x['aggregates'],indent=2))
