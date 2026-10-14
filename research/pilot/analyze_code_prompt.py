"""Recompute descriptive comparisons from published code-prompt artifacts.

No new score, model call, source selection or tuning. Paired counts use the
frozen test split; timing and graph sizes are descriptive single-run results.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent
BASE=HERE/'results'
OUT=BASE/'code-prompt'


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run_summary(base):
    execution=read(base/'execution.json')
    index=read(base/'index-summary.json')
    events=[e for e in execution['events'] if e['phase']=='index']
    assert sum(e['service']=='generation' for e in events)==execution['index_generation_attempts']
    dispatched=[e for e in events if e.get('request_dispatched') is not False]
    usage_unknown=[e['sequence'] for e in dispatched if 'usage' not in e]
    usage=Counter()
    for e in dispatched:
        for k,v in e.get('usage',{}).items():
            if type(v) is int:usage[e['service']+'_'+k]+=v
    operations={}
    for name in sorted({e['operation'] for e in events}):
        subset=[e for e in dispatched if e['operation']==name]
        operations[name]={'physical_attempts':len(subset),
            'initially_validated':sum(e['status']=='validated' and not e.get('recovery') for e in subset),
            'complete_reply_later_validated_and_reused':sum(bool(e.get('recovery')) for e in subset),
            'known_supervised_seconds':sum(e['elapsed_seconds'] for e in subset if 'elapsed_seconds' in e),
            'missing_supervised_timing_sequences':[e['sequence'] for e in subset if 'elapsed_seconds' not in e]}
    return {'index_tables':index['tables'],'entity_types':index['entity_type_counts'],
        'output_bytes':index['all_output_file_bytes'],'vector_bytes':index['vector_store_bytes'],
        'budget_generation_reservations':execution['index_generation_attempts'],
        'physical_generation_attempts':sum(e['service']=='generation' for e in dispatched),
        'new_embedding_batches':sum(e['service']=='embedding' for e in dispatched),
        'non_dispatched_reservations':[e['sequence'] for e in events if e.get('request_dispatched') is False],
        'unknown_usage_sequences':usage_unknown,'index_observed_usage_totals':dict(usage),
        'usage_scope':'Only phase=index for calls/usage/operations. Cumulative embedding reservations below also include prior probes and any query-vector preparation; not a per-run invoice.',
        'embedding_reserved_tokens_cumulative':execution['embedding_reserved_tokens'],
        'embedding_estimate_usd_cumulative':execution['known_embedding_input_estimate_usd'],
        'active_workflow_seconds':execution['active_index_workflow_seconds'],
        'diagnosed_stop_gap_seconds':execution['diagnosed_stop_gap_seconds'],
        'index_calendar_seconds':execution['index_elapsed_calendar_seconds'],
        'completion_cache_hits':execution['completion_cache_hits'],
        'operations':operations,'memory_measurement':execution['memory_measurement'],
        **({'host_interruption_timing':execution['host_interruption_timing']} if 'host_interruption_timing' in execution else {})}


def calculate():
    scores=read(OUT/'scores.json')
    paired=[]
    for budget in [4000,8000,12000,16000]:
        for baseline in ['bm25','hybrid','ms_basic','ms_local']:
            values=[p['code_minus_'+baseline] for p in scores['paired'] if p['split']=='test' and p['budget']==budget]
            assert len(values)==15
            paired.append({'budget':budget,'baseline':baseline,'scorable_test_questions':15,
                'wins':sum(v>0 for v in values),'ties':sum(v==0 for v in values),'losses':sum(v<0 for v in values),
                'mean_coverage80_difference':statistics.mean(values)})
    cases={qid:[r for r in scores['rows'] if r['question_id']==qid] for qid in ['Q01','Q07','Q13']}
    retrieval=read(OUT/'retrieval.json')
    assert len(retrieval['records'])==80 and retrieval['external_calls']==0
    size_files=[BASE/'execution.json',BASE/'index-summary.json',OUT/'execution.json',OUT/'index-summary.json',OUT/'scores.json',OUT/'retrieval.json']
    return {'scope':'Descriptive single-run comparison on the same frozen sources, questions and scoring. Not a causal isolation of prompt or graph contribution, and not answer accuracy.',
        'source_sha256':{str(p.relative_to(HERE)):sha(p) for p in size_files},
        'runs':{'default':run_summary(BASE),'code_prompt':run_summary(OUT)},
        'test_aggregates':[r for r in scores['aggregates'] if r['split']=='test'],
        'paired_test_counts':paired,'preselected_case_scores':cases,
        'offline_retrieval':{'contexts':80,'new_provider_calls':0,
            'elapsed_seconds':retrieval['elapsed_seconds'],'community_level':retrieval['community_level'],
            'dropped_tail_rows':sum(r['dropped_tail_rows'] for r in retrieval['records']),
            'shared_source_vector_sha256':retrieval['shared_vector_sha256']},
        'limitations':['One fixed repository and15 scorable test questions; no population significance claim.',
            'Old baselines are preserved; new graph built after inspecting their failures.',
            'Mixed60/120-second timeouts, unified bounded transient retries, removed total deadline and authorized generation cap1200→1600 are disclosed execution changes.',
            'No equal-actual-source-token or randomized graph control was added in this variant.',
            'Missing provider usage remains unknown; no generation invoice or measured memory figure.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    result=calculate();path=OUT/'analysis.json'
    if args.check:assert result==read(path)
    else:path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'contexts':result['offline_retrieval']['contexts'],'paired_test_comparisons':len(result['paired_test_counts']),'new_model_calls':0}))
