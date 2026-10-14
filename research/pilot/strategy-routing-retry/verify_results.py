"""Public, stdlib-only verification; does not read private cache or credentials."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=HERE/'results';OLD=HERE.parent/'strategy-routing'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=read(HERE/'live-readiness.json')
    for name,value in manifest['sha256'].items():assert sha(HERE/name)==value,('changed frozen retry file',name)
    inherit=read(HERE/'inherited-manifest.json');old=read(OLD/'results/execution.json');execution=read(OUT/'execution.json')
    assert inherit['old_summary_sha256']==old['private_summary_sha256'] and inherit['carry']==old['counts']==execution['carry']
    assert execution['original_execution_sha256']==sha(OLD/'results/execution.json')
    qids={'Q08','Q10','Q11','Q14','Q16','Q18'};assert {c['question_id'] for c in execution['cells']}==qids and len(execution['cells'])==6
    original={c['question_id']:c for c in old['cells'] if c['method']=='routed_graphrag'}
    assert all(original[q]['status']=='failed' for q in qids)
    counts=dict(execution['carry']);cell_inputs={q:inherit['cells'][q+':routed_graphrag']['generation_input_tokens'] for q in qids};attempts=Counter();bycell={q:[] for q in qids}
    for seq,event in enumerate(execution['events'],1):
        assert seq==event['sequence'];q=event['cell'].split(':')[0];assert q in qids and event['cell']==q+':routed_graphrag'
        wire=read(OUT/f'wire/event-{seq:03}.json');assert wire['event']==event;body=wire['request']['body'];service=event['service'];assert wire['request']['service']==service
        canonical=json.dumps(body,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();assert hashlib.sha256(canonical).hexdigest()==event['request_body_sha256']
        keybody=json.dumps({'service':service,'body':body},sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();assert hashlib.sha256(keybody).hexdigest()==event['key']
        if service=='generation':
            assert body['model']=='gpt-5.6-luna' and body['max_output_tokens']==2048 and body['stream'] is True and body['num_retries']==0
            assert event['stage'] in {'primer','local','reduce'} and event['input_tokens']<=16000
            counts['generation_reservations']+=1;counts['generation_input_tokens']+=event['input_tokens'];cell_inputs[q]+=event['input_tokens']
            if event['stage']=='primer':assert event['key'] in inherit['cells'][event['cell']]['requests']
        else:
            assert service=='embedding' and body['model']=='text-embedding-3-large' and body['dimensions']==3072 and len(body['input'])==1 and event['input_tokens']<=8000
            counts['embedding_attempts']+=1;counts['embedding_tokens']+=event['input_tokens']
            reply=wire['response_envelope'].get('response');assert reply is None or reply.get('vectors_omitted') is True
        attempts[event['key']]+=1
        prior=inherit['cells'][event['cell']]['requests'].get(event['key'],{}).get('prior_attempts',0);assert attempts[event['key']]+prior<=3
        env=wire['response_envelope'];assert not {'headers','raw','reasoning'}&set(env)
        if env.get('raw_response_file'):
            assert len(env['raw_response_sha256'])==64 and env['stored_raw_bytes']<=env['response_byte_limit']+1
            assert env['raw_complete']==(env['response_bytes']<=env['response_byte_limit'])
        bycell[q].append(event)
    assert counts==execution['counts'] and counts['generation_reservations']<=1883 and counts['generation_input_tokens']<=8000000
    assert counts['embedding_tokens']*.13/1000000<=1 and counts['embedding_attempts']<=1000
    for c in execution['cells']:
        q=c['question_id'];cell=read(OUT/c['cell_file']);assert cell['qid']==q and cell['method']=='routed_graphrag' and cell['route']=='drift'
        assert cell_inputs[q]==cell['generation_input_tokens']==c['generation_input_tokens_reserved_including_old_failed_attempts']<=64000
        assert hashlib.sha256((cell.get('answer') or '').encode()).hexdigest()==c['answer_sha256']
        uses=[u for u in cell['uses'] if u.get('origin_run')];assert len({u['key'] for u in uses})==2 and {u['stage'] for u in uses}=={'hyde','query_embedding'}
        for u in uses:
            assert u['key'] in inherit['cells'][q+':routed_graphrag']['requests'] and u['cache'] is True
        logical=Counter()
        for key in {e['key'] for e in bycell[q] if e['service']=='generation'}:
            logical[next(e['stage'] for e in bycell[q] if e['key']==key)]+=1
        assert logical['primer']==1 and logical['local']<=4 and logical['reduce']<=1
    subprocess.run([sys.executable,str(HERE/'aggregate_results.py'),'--check'],check=True,stdout=subprocess.DEVNULL)
    oldrows={(r['question_id'],r['method']):r for r in read(OLD/'results/scores.json')['rows']}
    newrows=read(OUT/'scores.json')['rows'];assert len(newrows)==92
    assert sum(r==oldrows[r['question_id'],r['method']] for r in newrows)==86
    if (OUT/'export-manifest.json').exists():
        for name,value in read(OUT/'export-manifest.json')['files'].items():assert sha(OUT/name)==value
    print(json.dumps({'status':'passed','retry_cells':6,'unchanged_successful_cells':86,'new_events':len(execution['events']),'cumulative_counts':counts,'private_cache_read':False,'api_calls':0}))
if __name__=='__main__':main()
