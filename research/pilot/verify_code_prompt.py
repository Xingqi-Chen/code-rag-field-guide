"""Offline validation of frozen code-prompt protocol and published interrupted run.

The partial execution has no retrieval score. Only stdlib, no private credentials.
"""
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/pilot/results/code-prompt'


def no_network(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'}:
        raise RuntimeError('Offline verification forbids networking')


sys.addaudithook(no_network)

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen=read(OUT/'preflight.json')
    for name,digest in frozen['frozen_files'].items():assert sha(ROOT/name)==digest,name
    assert frozen['generation_cache_entries']==0 and frozen['reused_source_query_vectors']==134
    x=read(OUT/'execution-interrupted.json');es=x['events']
    assert x['status']=='stopped' and x['stop_reason']=='worker_wall_timeout'
    assert x['index_generation_attempts']==len(es)==75
    assert [e['sequence'] for e in es]==list(range(1,76))
    assert all(e['status']=='validated' for e in es[:-1]) and es[-1]['status']=='failed'
    assert es[-1]['error_category']=='worker_wall_timeout' and 'usage' not in es[-1]
    assert Counter(e['operation'] for e in es)=={'extraction_initial':38,'extraction_glean':37}
    totals=Counter()
    for e in es[:-1]:
        for k,v in e['usage'].items():
            if type(v) is int:totals['generation_'+k]+=v
    assert dict(totals)==x['observed_usage_totals']
    assert x['embedding_attempts']==0 and x['embedding_reserved_tokens']==206333
    assert Decimal(x['known_embedding_input_estimate_usd'])==Decimal(206333)*Decimal('.13')/1000000
    assert not x['evaluation_complete']
    diagnosis=read(OUT/'timeout-diagnosis.json')
    assert diagnosis['unknown_event']==75 and diagnosis['new_calls_in_diagnosis']==0
    assert diagnosis['unknown_request_body_sha256']==es[-1]['request_body_sha256']
    assert len(diagnosis['cache_verification'])==74
    for e,c in zip(es[:-1],diagnosis['cache_verification'],strict=True):
        assert c['sequence']==e['sequence'] and c['request_body_sha256']==e['request_body_sha256']
    second=read(OUT/'execution-interrupted-02.json');events=second['events']
    assert second['status']=='stopped' and second['stop_reason']=='worker_wall_timeout'
    assert len(events)==second['index_generation_attempts']==96 and events[:75]==es
    assert [e['sequence'] for e in events if e['status']=='failed']==[75,96]
    valid=[e for e in events if e['status']=='validated'];assert len(valid)==94
    assert all('usage' not in events[i-1] for i in [75,96])
    assert second['unknown_usage_sequences']==[75,96] and second['limits']==x['limits']
    assert second['generation_input_tokens']==sum(e['input_tokens'] for e in events)
    assert second['embedding_attempts']==0 and second['embedding_reserved_tokens']==206333
    assert second['completion_cache_hits']==74
    totals=Counter()
    for e in valid:
        for k,v in e['usage'].items():
            if type(v) is int:totals['generation_'+k]+=v
    assert dict(totals)==second['observed_usage_totals']
    recovery=second['recoveries'];assert len(recovery)==1
    assert recovery[0]['event']==75 and recovery[0]['retry_event']==76
    assert events[74]['request_body_sha256']==events[75]['request_body_sha256']
    assert events[75]['status']=='validated' and recovery[0]['explicit_one_time_retry_authorized']
    progress=read(OUT/'recovery-progress.json')
    assert progress['retry_event']['request_body_sha256']==events[75]['request_body_sha256']
    assert progress['retry_event']['usage']==events[75]['usage'] and progress['lineage']==recovery[0]
    next_diagnosis=read(OUT/'timeout-diagnosis-02.json')
    assert next_diagnosis['unknown_event']==96 and next_diagnosis['successful_cached_responses']==94
    assert next_diagnosis['unknown_request_body_sha256']==events[-1]['request_body_sha256']
    for e,c in zip(valid,next_diagnosis['cache_verification'],strict=True):
        assert c['sequence']==e['sequence'] and c['request_body_sha256']==e['request_body_sha256']
    third=read(OUT/'execution-interrupted-03.json');latest=third['events']
    assert third['status']=='stopped' and third['stop_reason']=='worker_wall_timeout'
    assert len(latest)==third['index_generation_attempts']==107 and latest[:96]==events
    assert [e['sequence'] for e in latest]==list(range(1,108))
    assert [e['sequence'] for e in latest if e['status']=='failed']==[75,96,107]
    validated=[e for e in latest if e['status']=='validated'];assert len(validated)==104
    assert Counter(e['operation'] for e in validated)=={'extraction_initial':52,'extraction_glean':52}
    assert all('usage' not in latest[i-1] for i in [75,96,107])
    assert third['unknown_usage_sequences']==[75,96,107] and third['limits']==x['limits']
    assert third['started_utc']==x['started_utc'] and not third['evaluation_complete']
    assert third['generation_input_tokens']==sum(e['input_tokens'] for e in latest)==265846
    assert third['embedding_attempts']==0 and third['embedding_reserved_tokens']==206333
    assert third['completion_cache_hits']==168
    totals=Counter()
    for e in validated:
        for k,v in e['usage'].items():
            if type(v) is int:totals['generation_'+k]+=v
    assert dict(totals)==third['observed_usage_totals']
    recoveries=third['recoveries'];assert len(recoveries)==2 and recoveries[:1]==recovery
    assert recoveries[1]['event']==96 and recoveries[1]['retry_event']==97
    assert recoveries[1]['explicit_one_time_retry_authorized']
    assert latest[95]['request_body_sha256']==latest[96]['request_body_sha256']
    assert latest[96]['status']=='validated'
    authorization=read(OUT/'retry-authorization-02.json')
    assert authorization['unknown_event']==96 and authorization['allowed_replays']==1
    assert not authorization['budgets_reset']
    progress2=read(OUT/'recovery-progress-02.json')
    for k,v in progress2['retry_event'].items():assert latest[96][k]==v,k
    assert progress2['lineage']==recoveries[1] and progress2['prior_lineage']==recoveries[0]
    assert progress2['successful_cached_replies_reused_this_recovery']==94
    assert progress2['cumulative_cache_hits_at_recovery']==168
    last_diagnosis=read(OUT/'timeout-diagnosis-03.json')
    assert last_diagnosis['unknown_event']==107 and last_diagnosis['successful_cached_responses']==104
    assert last_diagnosis['new_calls_in_diagnosis']==0
    assert last_diagnosis['unknown_request_body_sha256']==latest[-1]['request_body_sha256']
    assert authorization['original_deadline_utc']==progress2['original_deadline_utc']==last_diagnosis['original_deadline_utc']
    for e,c in zip(validated,last_diagnosis['cache_verification'],strict=True):
        assert c['sequence']==e['sequence'] and c['request_body_sha256']==e['request_body_sha256']
    pending_review=read(OUT/'recovery-review-03.json')
    assert not pending_review['event107_authorization_received']
    assert pending_review['real_model_calls']==pending_review['real_ledger_mutations']==0
    sample=read(OUT/'quality-sample-default.json');review=read(OUT/'quality-review-default.json')
    assert sha(OUT/'quality-sample-default.json')==review['inputs']['sample_sha256']
    units={u['ms_text_unit_id']:u for u in read(ROOT/'research/pilot/results/index/text-unit-provenance.json')}
    for kind in ['entities','relationships']:
        rows=read(ROOT/f'research/pilot/results/index/{kind}.json')
        digest=lambda r:hashlib.sha256(f"20261012:{kind}:{r['id']}".encode()).hexdigest()
        chosen=sorted(rows,key=digest)[:20]
        assert [r['record'] for r in sample[kind]]==chosen
        assert len(review[kind])==20
        for chosen_record,item,judged in zip(chosen,sample[kind],review[kind],strict=True):
            assert item['sample_hash']==judged['sample_hash']==digest(chosen_record)
            assert chosen_record['id']==judged['id']
            assert item['sources']==[{'title':units[u]['title'],'input_id':units[u]['id']} for u in chosen_record['text_unit_ids']]
            assert judged['judgment'] in {'supported','partial_or_ambiguous','unsupported'}
            linked={s['input_id']:s['title'] for s in item['sources']}
            assert judged['evidence']
            for e in judged['evidence']:assert linked[e['input_id']]==e['source_title'] and e['snippet']
    assert not review['reviewer']['human_review'] and not review['reviewer']['blind_review']
    print('Verified frozen inputs, three interruption snapshots, 104 successful generations and 3 unknown outcomes, approved75-to76 and96-to97 retry lineage, unchanged cumulative limits and 40 baseline audit records. No new retrieval claim or model call.')


if __name__=='__main__':main()
