"""Publish visible retry results; never copy raw SSE, reasoning or vectors."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OLD=HERE.parent/'strategy-routing';RUN=ROOT/'.cache/pilot/strategy-routing-retry-20261014';OUT=HERE/'results'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
th=lambda s:hashlib.sha256(s.encode()).hexdigest()
def write(p,x):
    s=json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert str(ROOT) not in s and str(Path.home()) not in s
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
def export():
    state=read(RUN/'summary.json');assert state['status'] in {'complete','complete_with_recorded_failures'} and not state['synthetic']
    queries={q['id']:q for q in read(OLD/'queries.json')};calls={};records=[];pack=[]
    for e in state['events']:
        seq=e['sequence'];req=read(RUN/f'request-{seq:02}.json');env=read(RUN/f'response-{seq:02}.json')
        if req['service']=='embedding' and 'response' in env:
            reply=env['response'];env={**env,'response':{'model':reply.get('model'),'usage':reply.get('usage'),'vectors_omitted':True,'vector_count':len(reply.get('data',[])),'dimensions':[len(x.get('embedding',[])) for x in reply.get('data',[])]},'private_complete_response_sha256':sha(RUN/f'response-{seq:02}.json')}
        # Raw response file is private; only its digest and allowlisted diagnostics are public.
        assert not any(k in env for k in ('raw','headers','reasoning'))
        wire={'event':e,'request':req,'response_envelope':env};write(OUT/f'wire/event-{seq:03d}.json',wire)
        calls[seq]=wire
    for n,(key,c) in enumerate(state['cells'].items(),1):
        actual=[(e['sequence'],state['requests'][e['key']]['body']) for e in state['events'] if e['cell']==key and e['service']=='generation' and calls[e['sequence']]['response_envelope'].get('http_status')==200]
        sources=[];seen=set();exposures=[]
        for ev in c['evidence']:
            contexts=ev['context'] if isinstance(ev['context'],list) else [ev['context']]
            for context in contexts:
                seqs=[seq for seq,body in actual if context and any(context in m['content'][0]['text'] for m in body['input'])]
                exposures.append({'evidence_key':ev['evidence_key'],'context_sha256':th(context),'new_http200_generation_event_sequences':seqs})
                if seqs:
                    for source in ev.get('sources',[]):
                        if source['text_unit_id'] not in seen:sources.append(source);seen.add(source['text_unit_id'])
        public={**c,'actual_context_exposure':exposures,'raw_sources_in_http200_contexts':sources};name=f"cells/{c['qid']}-routed_graphrag.json";write(OUT/name,public)
        es=[e for e in state['events'] if e['cell']==key];gs=[e for e in es if e['service']=='generation'];known=[e['usage'] for e in gs if isinstance(e.get('usage'),dict)]
        record={'question_id':c['qid'],'method':c['method'],'route':c['route'],'status':c['status'],'failure':c.get('failure'),'answer_sha256':th(c.get('answer') or ''),'cell_file':name,
            'generation_input_tokens_reserved_including_old_failed_attempts':c['generation_input_tokens'],'old_generation_input_tokens':c['prior_generation_input_tokens'],
            'new_generation_input_tokens':sum(e['input_tokens'] for e in gs),'new_generation_reservations':len(gs),'new_embedding_attempts':sum(e['service']=='embedding' for e in es),
            'known_provider_input_tokens_new':sum(u['prompt_tokens'] for u in known),'known_provider_output_tokens_new':sum(u['completion_tokens'] for u in known),
            'provider_usage_unknown_new_generation_events':sum(e.get('usage') is None for e in gs),'elapsed_seconds_new':c['elapsed_seconds'],
            'inherited_cache_uses':sum(bool(u.get('origin_run')) for u in c['uses']),'raw_sources_in_http200_contexts':sources}
        records.append(record);pack.append({'anonymous_id':f'R{n:03}','question_id':c['qid'],'query':queries[c['qid']]['query'],'answer':c.get('answer') or '',
            'answer_sha256':record['answer_sha256'],'status':'completed' if c['status']=='complete' else 'failed'})
    public={k:v for k,v in state.items() if k not in {'requests','cells','supervisor_pid'}}
    public.update(private_summary_sha256=sha(RUN/'summary.json'),cells=records,completion_counts=dict(Counter(c['status'] for c in state['cells'].values())),
        original_execution_sha256=sha(OLD/'results/execution.json'),note='Separate retry; old failures, spend and 86 successful cells preserved. Raw SSE private; visible normalized responses and text-free diagnostics only.')
    write(OUT/'execution.json',public);random.Random(20261012).shuffle(pack)
    write(OUT/'blind-content-pack.json',{'rubric_sha256':sha(OLD/'answer-gold.json'),'rows':pack})
    print(json.dumps({'cells':len(records),'new_events':len(state['events']),'status':state['status']}))
if __name__=='__main__':export()
