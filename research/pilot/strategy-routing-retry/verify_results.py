"""Public, stdlib-only verification; does not read private cache or credentials."""
from collections import Counter
from datetime import datetime
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
        assert type(event['input_tokens']) is int and event['input_tokens']>0
        if service=='generation':
            assert body['model']=='gpt-5.6-luna' and body['max_output_tokens']==2048 and body['stream'] is True and body['num_retries']==0
            basekeys={'model','input','max_output_tokens','store','stream','num_retries','fallbacks','context_window_fallback_dict','caching'}
            assert body['store'] is False and body['fallbacks']==[] and body['context_window_fallback_dict']=={} and body['caching'] is False
            assert set(body)==basekeys|({'text'} if event['stage'] in {'primer','local'} else set())
            if event['stage']=='local':assert body['text']=={'format':{'type':'json_object'}}
            if event['stage']=='primer':
                inherited=inherit['cells'][event['cell']]['requests'][event['key']]
                assert len(inherited['old_events'])==1
                oldwire=read(OLD/f"results/wire/event-{inherited['old_events'][0]:03}.json")
                assert body==oldwire['request']['body']
            assert event['stage'] in {'primer','local','reduce'} and event['input_tokens']<=16000
            counts['generation_reservations']+=1;counts['generation_input_tokens']+=event['input_tokens'];cell_inputs[q]+=event['input_tokens']
            if event['stage']=='primer':assert event['key'] in inherit['cells'][event['cell']]['requests']
        else:
            assert service=='embedding' and body['model']=='text-embedding-3-large' and body['dimensions']==3072 and len(body['input'])==1 and event['input_tokens']<=8000
            assert set(body)=={'model','input','dimensions','encoding_format'} and body['encoding_format']=='float'
            counts['embedding_attempts']+=1;counts['embedding_tokens']+=event['input_tokens']
            reply=wire['response_envelope'].get('response');assert reply is None or reply.get('vectors_omitted') is True
        attempts[event['key']]+=1
        prior=inherit['cells'][event['cell']]['requests'].get(event['key'],{}).get('prior_attempts',0);assert attempts[event['key']]+prior<=3
        env=wire['response_envelope'];assert not {'headers','raw','reasoning'}&set(env)
        if event['status']=='validated':
            assert env.get('http_status')==event.get('http_status')==200 and 'response' in env
            assert env['response']['usage']==event['usage']
            reply=env['response'];usage=event['usage']
            assert all(type(v) is int and v>=0 for v in usage.values())
            assert reply['model']==body['model']
            if service=='generation':
                assert set(usage)=={'prompt_tokens','completion_tokens','total_tokens'}
                assert usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']
                assert len(reply['choices'])==1 and reply['choices'][0]['finish_reason']=='stop'
                assert set(reply['choices'][0]['message'])=={'content'} and isinstance(reply['choices'][0]['message']['content'],str) and reply['choices'][0]['message']['content'].strip()
                assert type(event['visible_output_common_tokens']) is int and event['visible_output_common_tokens']>0
                assert type(event['requested_output_limit_exceeded']) is bool
                assert event['requested_output_limit_exceeded']==(event['visible_output_common_tokens']>2048 or usage['completion_tokens']>2048)
            else:
                assert set(usage)=={'prompt_tokens','total_tokens'} and usage['total_tokens']==usage['prompt_tokens']
                assert reply['vector_count']==1 and reply['dimensions']==[3072]
        else:
            assert event['status']=='failed' and env.get('error_category')==event.get('error_category')
        assert event.get('request_dispatched') is True
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
        generated=[e for e in bycell[q] if e['service']=='generation']
        assert c['new_generation_reservations']==len(generated)
        assert c['new_generation_input_tokens']==sum(e['input_tokens'] for e in generated)
        assert c['provider_usage_known_new_generation_events']==sum(e.get('usage') is not None for e in generated)
        assert c['provider_usage_unknown_new_generation_events']==sum(e.get('usage') is None for e in generated)
        assert c['new_run_cache_read_operations']==sum(u.get('cache') is True for u in cell['uses'])
        assert c['elapsed_seconds_query_segments_new']==sum(s['elapsed_seconds'] for s in cell['execution_segments'])
        assert c['elapsed_seconds_new']==c['elapsed_seconds_query_segments_new']+c['recovery_prefetch_wall_seconds_new']
        assert c['recovery_prefetch_wall_seconds_new']==sum(i['wall_seconds'] for i in c['recovery_prefetch_intervals'])
        if q=='Q10':
            assert len(c['recovery_prefetch_intervals'])==2
            for interval,session,segment,seq in zip(c['recovery_prefetch_intervals'],execution['execution_sessions'][1:],cell['execution_segments'][1:],(13,16)):
                assert interval['prefetch_event_sequence']==seq and interval['started_utc']==session['started_utc'] and interval['finished_utc']==segment['started_utc']
                assert interval['wall_seconds']==(datetime.fromisoformat(interval['finished_utc'])-datetime.fromisoformat(interval['started_utc'])).total_seconds()
        else:assert c['recovery_prefetch_intervals']==[]
        # Reconstruct actual successful request exposure, not just assembled
        # candidates. Empty/untransmitted contexts cannot earn raw coverage.
        actual=[(e['sequence'],read(OUT/f"wire/event-{e['sequence']:03}.json")['request']['body'])
                for e in generated if e.get('http_status')==200]
        sources=[];seen=set();exposures=[]
        for evidence in cell['evidence']:
            contexts=evidence['context'] if isinstance(evidence['context'],list) else [evidence['context']]
            for context in contexts:
                seqs=[seq for seq,body in actual if context and any(context in m['content'][0]['text'] for m in body['input'])]
                exposures.append({'evidence_key':evidence['evidence_key'],'context_sha256':hashlib.sha256(context.encode()).hexdigest(),'new_http200_generation_event_sequences':seqs})
                if seqs:
                    for source in evidence.get('sources',[]):
                        if source['text_unit_id'] not in seen:sources.append(source);seen.add(source['text_unit_id'])
        assert exposures==cell['actual_context_exposure']
        assert sources==cell['raw_sources_in_http200_contexts']==c['raw_sources_in_http200_contexts']
        logical=Counter()
        for key in {e['key'] for e in bycell[q] if e['service']=='generation'}:
            logical[next(e['stage'] for e in bycell[q] if e['key']==key)]+=1
        assert logical['primer']==1 and logical['local']<=4 and logical['reduce']<=1
    subprocess.run([sys.executable,str(HERE/'aggregate_results.py'),'--check'],check=True,stdout=subprocess.DEVNULL)
    oldrows={(r['question_id'],r['method']):r for r in read(OLD/'results/scores.json')['rows']}
    newrows=read(OUT/'scores.json')['rows'];assert len(newrows)==92
    assert sum(r==oldrows[r['question_id'],r['method']] for r in newrows)==86
    subprocess.run([sys.executable,str(HERE/'aggregate_evidence.py'),'--check'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(HERE/'summarize_execution.py'),'--check'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(HERE/'build_evidence_pack.py'),'--check'],check=True,stdout=subprocess.DEVNULL)
    oldevidence={(r['question_id'],r['method']):r for r in read(OLD/'results/evidence-scores.json')['rows']}
    newevidence=read(OUT/'evidence-scores.json')['rows'];assert len(newevidence)==92
    assert sum(r==oldevidence[r['question_id'],r['method']] for r in newevidence)==86
    for name,seq,marker in (('transport-stop.json',12,'manual_retry_of'),('eof-stop.json',15,'reviewed_eof_retry_of')):
        assert read(HERE/name)['event']==execution['events'][seq-1]
        assert execution['events'][seq][marker]==seq
    pack_manifest=read(OUT/'evidence-packs/manifest.json')
    assert pack_manifest['content_review_sha256']==sha(HERE/'content-review.json')
    for row in pack_manifest['rows']:assert sha(OUT/'evidence-packs'/row['file'])==row['sha256']
    exported=read(OUT/'export-manifest.json')['files']
    actual={str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and p.name!='export-manifest.json'}
    assert set(exported)==actual,('incomplete export manifest',set(exported)^actual)
    for name,value in exported.items():assert sha(OUT/name)==value
    print(json.dumps({'status':'passed','retry_cells':6,'unchanged_successful_cells':86,'new_events':len(execution['events']),'cumulative_counts':counts,'private_cache_read':False,'api_calls':0}))
if __name__=='__main__':main()
