"""Check the completed variant's public ledger, graph and audit, offline."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from verify_code_prompt import no_network  # Installs the network-denying audit hook.
from index_artifacts import read_table, rows_sha
from code_prompt_json_syntax import candidate as tail_comma_candidate
from code_prompt_format_repair import candidate as format_candidate

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'results/code-prompt'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def graph_semantic_sha(rows):
    canonical=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    def semantic(row):
        result={k:v for k,v in row.items() if k not in {'id','human_readable_id'}}
        if result.get('text_unit_ids') is not None:result['text_unit_ids']=sorted(result['text_unit_ids'])
        return result
    return hashlib.sha256(canonical(sorted(canonical(semantic(row)) for row in rows)).encode()).hexdigest()


def main():
    for name,digest in read(OUT/'preflight.json')['frozen_files'].items():
        assert sha(ROOT/name)==digest, name
    s=read(OUT/'execution.json');events=s['events']
    assert s['status']=='index_complete' and s['wall_deadline_removed']
    assert s['limits']['wall_seconds'] is None and s['limits']['generation_request_seconds']==120
    assert [e['sequence'] for e in events]==list(range(1,len(events)+1))
    assert all(e['phase']=='index' for e in events)
    cap=read(OUT/'generation-cap-amendment.json')
    assert cap['previous_generation_cap']==1200 and cap['generation_cap']==1600
    assert cap['human_approval_utc']=='2026-10-14T00:31:24+00:00'
    assert cap['new_limits']=={**cap['previous_limits'],'generation_index_attempts':1600}
    assert s['limits']==cap['new_limits']
    assert s['index_generation_attempts']==sum(e['service']=='generation' for e in events)<=1600
    assert s['embedding_attempts']==sum(e['service']=='embedding' for e in events)
    assert s['generation_input_tokens']==sum(e['input_tokens'] for e in events if e['service']=='generation')<=8000000
    assert s['embedding_reserved_tokens']==206333+sum(e['input_tokens'] for e in events if e['service']=='embedding')
    assert Decimal(s['known_embedding_input_estimate_usd'])==Decimal(s['embedding_reserved_tokens'])*Decimal('.13')/1000000<=1
    assert s['non_dispatched_reservations']==[195,675]
    assert cap['non_dispatched_checkpoint_event']==675
    assert events[674]['request_dispatched'] is False and events[675]['status']=='validated'
    assert events[674]['request_body_sha256']==events[675]['request_body_sha256']
    dispatched=[e for e in events if e.get('request_dispatched') is not False]
    assert dict(Counter(e['service'] for e in dispatched))==s['provider_dispatch_attempts']
    assert [e['sequence'] for e in dispatched if 'usage' not in e]==s['unknown_usage_sequences']
    assert {75,96,107,108,109,272,623}<=set(s['unknown_usage_sequences'])
    usage=Counter()
    for e in events:
        for k,v in e.get('usage',{}).items():
            if type(v) is int:usage[e['service']+'_'+k]+=v
    assert dict(usage)==s['observed_usage_totals']
    valid=[e for e in events if e['status']=='validated']
    assert len({e['request_body_sha256'] for e in valid if e['service']=='generation'})==sum(e['service']=='generation' for e in valid)
    counts=Counter(e['operation'] for e in valid)
    assert counts['extraction_initial']==counts['extraction_glean']==114
    host=read(OUT/'host-recovery-554.json');e=events[553]
    assert e['request_body_sha256']==host['event']['request_body_sha256']
    assert e['usage']==host['event']['usage']=={'prompt_tokens':1811,'completion_tokens':97,'total_tokens':1908}
    assert e['validation_stage']=='offline_recovery_after_executor_transport_loss' and 'elapsed_seconds' not in e
    assert not host['cumulative_caps_reset'] and not host['policy_changed']
    assert host['recovery']['new_calls_for_recovery']==0
    assert s['host_interruption_timing']['actual_process_end_utc'] is None
    assert 554 in s['request_timing']['missing_supervised_timing_sequences']
    syntax=read(OUT/'schema-1027-amendment.json');diagnosis=read(OUT/'schema-1027-diagnosis.json')
    assert syntax['human_approval_utc']=='2026-10-14T01:03:05+00:00'
    assert syntax['approved_single_format_exception'] and syntax['event']==1027
    assert syntax['new_provider_calls_for_repair']==0 and syntax['not_general_json_or_semantic_repair']
    assert syntax['removed_character_offsets_zero_based']==[1595,2236,2876,3461]
    assert s['schema_format_exceptions']==[syntax]
    assert s['schema_exception_applications'] and all(a['original_event']==1027 and a['provider_calls_for_repair']==0
        for a in s['schema_exception_applications'])
    assert events[1026]['usage']==syntax['original_usage']==diagnosis['usage']
    assert sum(e['request_body_sha256']==syntax['request_body_sha256'] for e in events)==1
    assert events[1026]['schema_syntax_exception']['candidate_content_sha256']==diagnosis['candidate_content_sha256']
    assert 'recovery' not in events[1026]  # Transport validation/usage already succeeded before syntax failure.
    policy=read(OUT/'json-tail-comma-amendment.json')
    assert s['json_tail_comma_policy']==policy and policy['human_approval_utc']=='2026-10-14T01:27:36+00:00'
    assert policy['limits_before']==policy['limits_after']==s['limits']
    assert policy['transient_retry_policy_unchanged'] and not policy['total_deadline_reintroduced']
    repairs=s['json_syntax_repairs'];assert any(r['original_event']==1091 for r in repairs)
    assert len({r['original_event'] for r in repairs})==len(repairs)
    for repair in repairs:
        path=OUT/repair['evidence_file'];assert sha(path)==repair['evidence_sha256']
        record=read(path);original=record['original_content'];fixed,offsets,strings=tail_comma_candidate(original)
        assert fixed==record['candidate_content'] and offsets==record['removed_character_offsets_zero_based']
        assert offsets and tail_comma_candidate(fixed)[2]==strings
        assert hashlib.sha256(original.encode()).hexdigest()==record['original_content_sha256']
        assert hashlib.sha256(fixed.encode()).hexdigest()==record['candidate_content_sha256']
        try:json.loads(original)
        except json.JSONDecodeError:pass
        else:raise AssertionError('Valid JSON must not pass through the repair path')
        assert isinstance(json.loads(fixed),dict) and record['original_schema_validated']
        event=events[record['original_event']-1]
        assert event['usage']==record['original_usage'] and record['provider_calls_for_repair']==0
        assert event['request_body_sha256']==record['request_body_sha256']
        assert event['schema_syntax_exception']['evidence_file']==repair['evidence_file']
        matching=[e for e in events if e['request_body_sha256']==record['request_body_sha256']]
        assert sum(e['status']=='validated' for e in matching)==1
        assert max(e['sequence'] for e in matching)==record['original_event']  # Never resend after complete reply.
    format_policy=read(OUT/'json-format-amendment.json')
    assert s['json_format_policy']==format_policy and format_policy['human_approval_utc']=='2026-10-14T01:51:30+00:00'
    assert format_policy['limits_before']==format_policy['limits_after']==s['limits']
    assert format_policy['transient_retry_policy_unchanged'] and not format_policy['total_deadline_reintroduced']
    formats=s['json_format_repairs'];assert any(r['original_event']==1147 for r in formats)
    assert len({r['original_event'] for r in formats})==len(formats)
    for repair in formats:
        path=OUT/repair['evidence_file'];assert sha(path)==repair['evidence_sha256']
        record=read(path);original=record['original_content'];fixed,edits,spans=format_candidate(original)
        assert fixed==record['candidate_content'] and edits==record['exact_edits'] and spans==record['inline_code_spans']
        assert hashlib.sha256(original.encode()).hexdigest()==record['original_content_sha256']
        assert hashlib.sha256(fixed.encode()).hexdigest()==record['candidate_content_sha256']
        assert record['original_schema_validated'] and record['each_edit_necessary_for_json_validity']
        event=events[record['original_event']-1]
        assert event['usage']==record['original_usage'] and record['provider_calls_for_repair']==0
        assert event['request_body_sha256']==record['request_body_sha256']
        assert event['schema_syntax_exception']['evidence_file']==repair['evidence_file']
        matching=[e for e in events if e['request_body_sha256']==record['request_body_sha256']]
        assert sum(e['status']=='validated' for e in matching)==1
        assert max(e['sequence'] for e in matching)==record['original_event']
        if record['original_event']==1147:
            diagnosis=read(OUT/'schema-1147-diagnosis.json')
            assert fixed==diagnosis['candidate_content'] and all(e['delete']=='' and e['insert']=='\\' for e in edits)
    index=read(OUT/'index-summary.json');sample=read(OUT/'quality-sample.json')
    fixed_review=read(OUT/'fixed-graph-review.json')
    for kind in ['entities','relationships','communities','community_reports']:
        rows=read_table(OUT/f'index/{kind}.json')
        assert len(rows)==index['tables'][kind]['rows'] and len({r['id'] for r in rows})==len(rows)
        assert rows_sha(rows)==index['tables'][kind]['public_json_layout']['logical_rows_sha256']
        if kind in ['entities','relationships']:
            assert graph_semantic_sha(rows)==fixed_review['whole_graph_semantic_sha256'][kind]
            ordered=sorted(rows,key=lambda r:hashlib.sha256(f"20261012:{kind}:{r['id']}".encode()).hexdigest())
            assert [r['record'] for r in sample['samples']['code-prompt'][kind]]==ordered[:20]
    assert dict(Counter(r['type'] for r in read_table(OUT/'index/entities.json')))==index['entity_type_counts']
    parser=read(OUT/'concatenation-diagnostics.json')
    assert parser['new_model_calls']==0
    for run in parser['runs'].values():
        assert run['chunks']==len(run['rows'])==114
        for key in ['entity_record_count_gap','relationship_record_count_gap']:
            assert run[key]==sum(r[key] for r in run['rows'])
    from verify_results import validate
    retrieval=validate(out=OUT,budgets=(4000,8000,12000,16000),
        include_features=False,methods=['ms_local_code_prompt'])
    assert len(retrieval['records'])==80 and retrieval['external_calls']==0
    assert retrieval['query_vector_sha256']==read(HERE/'results/budget-supplement/retrieval.json')['query_vector_sha256']
    print('Verified completed ledger, cumulative budgets, unknown usage/timing, graph counts, fixed sample and80 offline contexts. No model calls.')


if __name__=='__main__':main()
