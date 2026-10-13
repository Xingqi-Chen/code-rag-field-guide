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
    previous=third
    for number,sequence,cache_hits in [(4,108,272),(5,109,376)]:
        current=read(OUT/f'execution-interrupted-{number:02}.json')
        assert current['status']=='stopped' and current['stop_reason']=='worker_wall_timeout'
        assert current['events'][:-1]==previous['events']
        assert current['index_generation_attempts']==len(current['events'])==sequence
        assert current['completion_cache_hits']==cache_hits
        assert current['limits']==third['limits'] and current['started_utc']==third['started_utc']
        assert current['embedding_attempts']==0 and current['embedding_reserved_tokens']==206333
        assert current['generation_input_tokens']==sum(e['input_tokens'] for e in current['events'])
        assert current['observed_usage_totals']==third['observed_usage_totals']
        assert current['unknown_usage_sequences']==[75,96,*range(107,sequence+1)]
        last=current['events'][-1]
        assert last['status']=='failed' and last['error_category']=='worker_wall_timeout' and 'usage' not in last
        assert last['request_body_sha256']==latest[-1]['request_body_sha256']
        rs=current['recoveries'];assert len(rs)==number-1 and rs[:-1]==previous['recoveries']
        assert rs[-1]['event']==sequence-1 and rs[-1]['retry_event']==sequence
        assert rs[-1]['logical_retry_number']==number-3 and rs[-1]['backoff_seconds']==[5,15][number-4]
        policy=read(OUT/'timeout-retry-authorization.json')
        assert current['timeout_retry_policy']==policy
        assert policy['max_additional_retries_per_request_hash']==2
        assert policy['generation_request_seconds']==60
        previous=current
    amendment=read(OUT/'timeout-amendment-120.json')
    assert amendment['prior_generation_request_seconds']==60 and amendment['generation_request_seconds']==120
    assert amendment['first_possible_event']==110 and amendment['original_deadline_utc']==policy['original_deadline_utc']
    assert not amendment['cumulative_caps_reset'] and not amendment['deadline_extended']
    assert not amendment['request_body_prompt_model_corpus_parser_and_metrics_changed']
    resumed=read(OUT/'recovery-progress-120.json');event110=resumed['retry_event']
    assert event110['sequence']==110 and event110['status']=='validated' and event110['http_status']==200
    assert event110['request_body_sha256']==previous['events'][-1]['request_body_sha256']
    assert resumed['lineage']['event']==109 and resumed['lineage']['retry_event']==110
    assert resumed['lineage']['logical_retry_number']==3
    assert resumed['successful_generation_cache_reuse_this_recovery']==104
    assert resumed['cumulative_cache_hits_at_recovery']==480
    assert resumed['amendment_applied_utc']==amendment['applied_utc']
    assert 0<event110['elapsed_seconds']<60
    removal=read(OUT/'deadline-removal-applied.json')
    assert removal['total_wall_deadline_removed'] and not removal['cumulative_budgets_reset']
    assert removal['generation_request_seconds']==120 and removal['embedding_request_seconds']==30
    assert removal['non_dispatched_checkpoint_event']==195 and removal['first_possible_event']==196
    assert removal['policy']['max_additional_retries_per_request_hash']==2
    assert 'original_wall_deadline' not in removal['policy']['unchanged']
    assert removal['policy']['previous_deadline_utc']==policy['original_deadline_utc']
    progress=read(OUT/'deadline-removal-progress.json')
    checkpoint,continued=progress['safe_checkpoint'],progress['first_resumed_event']
    assert checkpoint['sequence']==195 and checkpoint['request_dispatched'] is False and checkpoint['policy_checkpoint']
    assert continued['sequence']==196 and continued['status']=='validated' and continued['http_status']==200
    assert checkpoint['request_body_sha256']==continued['request_body_sha256']
    assert progress['lineage']['event']==195 and progress['lineage']['retry_event']==196
    assert progress['lineage']['logical_retry_number']==0 and not progress['lineage']['remote_completion_and_cost_unknown']
    assert progress['successful_responses_reused']==189 and progress['cumulative_cache_hits_at_recovery']==669
    assert progress['unknown_usage_sequences_before_resume']==[75,96,107,108,109]
    assert progress['wall_deadline_removed'] and progress['limits']['wall_seconds'] is None
    stopped520=read(OUT/'execution-interrupted-07.json');events520=stopped520['events']
    assert stopped520['status']=='stopped' and stopped520['stop_reason']=='unclassified_http_error'
    assert len(events520)==stopped520['index_generation_attempts']==272
    assert events520[:109]==previous['events']
    assert events520[-1]['http_status']==520 and events520[-1]['response_format']=='non_json'
    assert events520[-1]['request_body_sha256']=='17b46a852d4e61e4321bfe32cf59a1fb5df5da1c4e2b3726d3e2356864465f36'
    assert stopped520['non_dispatched_reservations']==[195]
    assert stopped520['provider_dispatch_attempts']=={'generation':271}
    assert stopped520['unknown_usage_sequences']==[75,96,107,108,109,272]
    assert stopped520['generation_input_tokens']==sum(e['input_tokens'] for e in events520)==667096
    validated520=[e for e in events520 if e['status']=='validated']
    assert len(validated520)==265
    assert Counter(e['operation'] for e in validated520)=={'extraction_initial':114,'extraction_glean':114,'description_summary':37}
    totals=Counter()
    for e in validated520:
        for k,v in e['usage'].items():
            if type(v) is int:totals['generation_'+k]+=v
    assert dict(totals)==stopped520['observed_usage_totals']
    assert stopped520['embedding_attempts']==0 and stopped520['embedding_reserved_tokens']==206333
    assert stopped520['wall_deadline_removed'] and stopped520['limits']['wall_seconds'] is None
    assert stopped520['limits']['generation_request_seconds']==120
    assert stopped520['request_timing']['non_dispatched_supervised_seconds']==.214
    approved520=read(OUT/'http520-authorization.json')
    amendment520=read(OUT/'http520-retry-amendment.json')
    progress520=read(OUT/'http520-recovery-progress.json')
    assert approved520['human_approval_utc']==amendment520['human_approval_utc']==progress520['human_approval_utc']=='2026-10-13T16:18:23+00:00'
    assert amendment520['first_possible_event']==273 and amendment520['trigger_event']==272
    assert amendment520['explicit_separate_http520_recovery_approval_confirmed']
    assert not amendment520['cumulative_budgets_reset'] and not amendment520['total_deadline_reintroduced']
    assert approved520['timeout_and_http520_share_max_additional_attempts']==2
    continued520=progress520['successful_retry']
    assert continued520['sequence']==273 and continued520['status']=='validated' and continued520['http_status']==200
    assert continued520['request_body_sha256']==events520[-1]['request_body_sha256']
    assert progress520['lineage']['event']==272 and progress520['lineage']['retry_event']==273
    assert progress520['lineage']['reason']=='http520_without_complete_model_response'
    assert progress520['lineage']['authorization_utc']==approved520['human_approval_utc']
    assert progress520['successful_generation_cache_reuse_this_recovery']==265 and progress520['cumulative_cache_hits_at_recovery']==934
    assert progress520['prior_unknown_usage_sequences_retained']==stopped520['unknown_usage_sequences']
    host=read(OUT/'host-recovery-554.json');stopped503=read(OUT/'execution-interrupted-09.json')
    events503=stopped503['events'];diagnosis503=read(OUT/'http503-diagnosis.json')
    assert len(events503)==stopped503['index_generation_attempts']==623
    assert stopped503['status']=='stopped' and stopped503['stop_reason']=='model_related'
    assert events503[-1]['http_status']==503 and events503[-1]['error_category']=='model_related'
    assert stopped503['unknown_usage_sequences']==[75,96,107,108,109,272,623]
    assert stopped503['non_dispatched_reservations']==[195]
    assert stopped503['provider_dispatch_attempts']=={'generation':622}
    assert sum(e['status']=='validated' for e in events503)==diagnosis503['successful_generation_cache_entries_verified']==615
    event554=events503[553]
    assert event554['request_body_sha256']==host['event']['request_body_sha256']
    assert sum(e['request_body_sha256']==event554['request_body_sha256'] for e in events503)==1
    assert event554['usage']==host['event']['usage']=={'prompt_tokens':1811,'completion_tokens':97,'total_tokens':1908}
    assert 'elapsed_seconds' not in event554 and host['recovery']['request_elapsed_seconds'] is None
    assert host['recovery']['new_calls_for_recovery']==0 and host['recovery']['successful_responses_reused']==547
    assert stopped503['request_timing']['missing_supervised_timing_sequences']==[554]
    assert stopped503['host_interruption_timing']['actual_process_end_utc'] is None
    assert stopped503['generation_input_tokens']==sum(e['input_tokens'] for e in events503)==755205
    assert stopped503['completion_cache_hits']==1481 and stopped503['embedding_attempts']==0
    assert stopped503['embedding_reserved_tokens']==206333 and stopped503['wall_deadline_removed']
    totals=Counter()
    for e in events503:
        for k,v in e.get('usage',{}).items():
            if type(v) is int:totals[e['service']+'_'+k]+=v
    assert dict(totals)==stopped503['observed_usage_totals']
    witnesses=read(OUT/'preindex-fixed-witnesses.json')
    old_witnesses=read(ROOT/'research/pilot/results/failure-analysis/extraction-witnesses.json')
    witness_review=read(OUT/'preindex-witness-review.json')
    parser_check=read(OUT/'preindex-official-parser-check.json')
    assert sha(OUT/'preindex-fixed-witnesses.json')==witness_review['input_files']['new_file_sha256']==parser_check['source_witness_sha256']
    assert sha(ROOT/'research/pilot/results/failure-analysis/extraction-witnesses.json')==witness_review['input_files']['old_file_sha256']
    assert len(witnesses['units'])==len(old_witnesses['units'])==len(parser_check['rows'])==4
    response_map={'old':{},'new':{}}
    for old_unit,new_unit in zip(old_witnesses['units'],witnesses['units'],strict=True):
        assert new_unit['title']==old_unit['title'] and new_unit['source_text']==old_unit['source_text']
        assert hashlib.sha256(new_unit['source_text'].encode()).hexdigest()==new_unit['source_text_sha256']
        assert len(new_unit['replies'])==2
        for reply in new_unit['replies']:
            assert hashlib.sha256(reply['content'].encode()).hexdigest()==reply['content_sha256']
            assert reply['request_body_sha256']==events520[reply['sequence']-1]['request_body_sha256']
        for label,unit in [('old',old_unit),('new',new_unit)]:
            for reply in unit['replies']:response_map[label][reply['sequence']]=reply['content']
    assert sum(len(case['findings']) for case in witness_review['case_reviews'])==14
    for case in witness_review['case_reviews']:
        for finding in case['findings']:
            for evidence in finding['response_evidence']:
                assert evidence['record_contains'] in response_map[evidence['run']][evidence['sequence']]
    assert all(r['entity_gap']==1 and r['relationship_gap']==0 for r in parser_check['rows'])
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
    print('Verified frozen inputs, historical timeout/HTTP520/HTTP503 snapshots,554 complete-reply recovery without replay, preserved cumulative caps and timing uncertainty, fixed witnesses and40 baseline audit records. No completed retrieval claim or model call.')


if __name__=='__main__':main()
