"""Check the completed variant's public ledger, graph and audit, offline."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from verify_code_prompt import no_network  # Installs the network-denying audit hook.

HERE=Path(__file__).resolve().parent
OUT=HERE/'results/code-prompt'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    s=read(OUT/'execution.json');events=s['events']
    assert s['status']=='index_complete' and s['wall_deadline_removed']
    assert s['limits']['wall_seconds'] is None and s['limits']['generation_request_seconds']==120
    assert [e['sequence'] for e in events]==list(range(1,len(events)+1))
    assert all(e['phase']=='index' for e in events)
    assert s['index_generation_attempts']==sum(e['service']=='generation' for e in events)<=1200
    assert s['embedding_attempts']==sum(e['service']=='embedding' for e in events)
    assert s['generation_input_tokens']==sum(e['input_tokens'] for e in events if e['service']=='generation')<=8000000
    assert s['embedding_reserved_tokens']==206333+sum(e['input_tokens'] for e in events if e['service']=='embedding')
    assert Decimal(s['known_embedding_input_estimate_usd'])==Decimal(s['embedding_reserved_tokens'])*Decimal('.13')/1000000<=1
    assert s['non_dispatched_reservations']==[195]
    dispatched=[e for e in events if e.get('request_dispatched') is not False]
    assert dict(Counter(e['service'] for e in dispatched))==s['provider_dispatch_attempts']
    assert [e['sequence'] for e in dispatched if 'usage' not in e]==s['unknown_usage_sequences']
    assert {75,96,107,108,109,272}<=set(s['unknown_usage_sequences'])
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
    index=read(OUT/'index-summary.json');sample=read(OUT/'quality-sample.json')
    for kind in ['entities','relationships','communities','community_reports']:
        rows=read(OUT/f'index/{kind}.json')
        assert len(rows)==index['tables'][kind]['rows'] and len({r['id'] for r in rows})==len(rows)
        if kind in ['entities','relationships']:
            ordered=sorted(rows,key=lambda r:hashlib.sha256(f"20261012:{kind}:{r['id']}".encode()).hexdigest())
            assert [r['record'] for r in sample['samples']['code-prompt'][kind]]==ordered[:20]
    assert dict(Counter(r['type'] for r in read(OUT/'index/entities.json')))==index['entity_type_counts']
    parser=read(OUT/'concatenation-diagnostics.json')
    assert parser['new_model_calls']==0
    for run in parser['runs'].values():
        assert run['chunks']==len(run['rows'])==114
        for key in ['entity_record_count_gap','relationship_record_count_gap']:
            assert run[key]==sum(r[key] for r in run['rows'])
    retrieval=read(OUT/'retrieval.json')
    assert len(retrieval['records'])==80 and retrieval['external_calls']==0
    assert retrieval['query_vector_sha256']==read(HERE/'results/budget-supplement/retrieval.json')['query_vector_sha256']
    print('Verified completed ledger, cumulative budgets, unknown usage/timing, graph counts, fixed sample and80 offline contexts. No model calls.')


if __name__=='__main__':main()
