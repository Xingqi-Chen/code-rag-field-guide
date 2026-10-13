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
    print('Verified frozen inputs, 75-event interrupted ledger with 1 unknown outcome, cumulative cost reserve and 40 fixed baseline audit records. No new retrieval claim or model call.')


if __name__=='__main__':main()
