"""Standard-library, offline checks of the routing preflight and frozen protocol."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

from routing_rules import route,call_bounds
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def deny_network(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'}:
        raise RuntimeError('Offline publication verification forbids networking')
sys.addaudithook(deny_network)
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    pre=read(HERE/'preflight.json');queries=read(HERE/'queries.json')
    assert pre['external_calls']==0 and pre['credentials_read'] is False and not pre['index_rebuilt']
    assert pre['status']=='offline_prepared_budget_confirmation_required'
    for name,digest in pre['source_sha256'].items():assert sha(ROOT/name)==digest,name
    main_q=read(HERE.parent/'questions.json');extra=read(HERE.parent/'global-questions.json')
    expected={q['id']:q['query'] for q in main_q+extra}
    assert {q['id']:q['query'] for q in queries}==expected and len(queries)==23
    assert all(q['route']==route(q['query']) for q in queries)
    assert all(q['cohorts']==(['main20'] if q['id'] in {i['id'] for i in main_q} else [])+
        (['supplement6'] if q['id'] in {i['id'] for i in extra} else []) for q in queries)
    counts=Counter(q['route']['method'] for q in queries)
    assert dict(counts)==pre['route_counts_unique']=={'local':8,'drift':13,'global':2}
    assert Counter(q['route']['method'] for q in queries if 'main20' in q['cohorts'])=={'local':8,'drift':12}
    budget=pre['budget'];bounds=call_bounds(counts,3,23,4)
    assert all(budget[k]==v for k,v in bounds.items())
    assert bounds['nominal_generation_max']==178
    assert budget['generation_limit_required_for_full_retry_bound']==1349+178*3==1883
    assert budget['generation_reservations_remaining']==1600-1349==251
    assert budget['generation_limit_increase_required']==283
    assert budget['new_common_input_hard_max']==23*4*64000
    assert budget['cumulative_common_input_hard_max']==1977136+23*4*64000<=8000000
    assert budget['embedding_new_items_max_no_retry']==13*5+3==68
    assert budget['embedding_tokens_max_with_retries']==68*8000*3
    assert Decimal(budget['embedding_cumulative_usd_hard_max'])==Decimal(658211+68*8000*3)*Decimal('.13')/1000000<1
    assert pre['drift_level2_reports_with_existing_embeddings']==367
    assert pre['global_level0_reports']==23 and pre['global_map_batches']==4
    assert len(read(HERE/'global-map-contexts.json')['chunks'])==4
    gold=read(HERE/'answer-gold.json');review=read(HERE/'answer-gold-review.json')
    assert sha(HERE/'answer-gold.json')==review['target_sha256']
    assert gold['question_sets']['main20_original']==main_q
    assert gold['question_sets']['supplement6_original']==extra
    assert gold['legacy_global_gold_verbatim']==read(HERE.parent/'global-gold.json')
    assert len(gold['items'])==23 and {x['id'] for x in gold['items']}==set(expected)
    assert all(x['question']['query']==expected[x['id']] and 3<=len(x['criteria'])<=6 for x in gold['items'])
    assert len(gold['question_sets']['main_test16_ids'])==16
    assert len(gold['question_sets']['retrieval_test15_ids'])==15
    assert all(x['passed'] for x in review['checks'])
    plan=read(HERE/'plan.json');audit=read(HERE/'budget-review.json');mock=read(HERE/'mock-result.json')
    assert plan['budget']==budget
    assert plan['status']=='awaiting_generation_cap_confirmation_before_any_paid_call'
    assert audit['status']=='preparation_arithmetic_and_official_call_bound_passed_execution_adapter_not_yet_reviewed'
    for name,key in [('preflight.json','preflight_sha256'),('prepare.py','prepare_sha256'),
        ('routing_rules.py','routing_rules_sha256'),('mock_drift.py','mock_sha256'),
        ('mock-result.json','mock_result_sha256')]:
        assert sha(HERE/name)==audit['evidence'][key],name
    assert mock['generation_calls']==7 and mock['embedding_calls_including_stub_local_queries']==5
    assert mock['new_model_or_embedding_api_calls']==0 and audit['external_api_calls']==0
    assert audit['budget_recalculation']['generation_limit_needed_for_full_retry_bound']==1883
    if (HERE/'freeze.json').exists():
        for name,digest in read(HERE/'freeze.json')['sha256'].items():assert sha(ROOT/name)==digest,name
    print('Verified text-only routing,23 unique queries,178 nominal/534 retry-bounded generation calls, cumulative budgets, frozen inputs. No API calls.')

if __name__=='__main__':main()
