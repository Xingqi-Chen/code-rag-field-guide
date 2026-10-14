"""Export visible experiment evidence and method-masked grading packs, offline."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUN=ROOT/'.cache/pilot/strategy-routing-20261014'
OUT=HERE/'results'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
text_sha=lambda text:hashlib.sha256(text.encode()).hexdigest()

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    # Altering visible text after hashing would invalidate answer/evidence
    # identities. Stop for review instead of silently redacting hashed text.
    if str(ROOT) in text or str(Path.home()) in text:
        raise ValueError('Private path in export; review before publication')
    path.write_text(text)

def export(*,partial=False):
    snapshot=(RUN/'summary.json').read_bytes()
    state=json.loads(snapshot)
    if not partial:assert state['status'] in {'complete','complete_with_recorded_failures'}
    assert state['synthetic'] is False
    envelopes={}
    for event in state['events']:
        seq=event['sequence'];path=RUN/f'response-{seq:02}.json'
        # Pending responses can arrive after this snapshot. Do not mix them
        # into its result, or read a concurrently written worker response.
        if event['status']!='reserved_before_dispatch' and path.exists():
            body=path.read_bytes();envelopes[seq]=json.loads(body)
            if event.get('recovered_completed_reply'):
                record=state['requests'][event['key']]
                assert record['completed_response']==path.name
                assert hashlib.sha256(body).hexdigest()==record['completed_sha256']
    def http200(event):
        envelope=envelopes.get(event['sequence'],{})
        return (envelope.get('http_status')==200 and
                (event.get('http_status')==200 or event.get('recovered_completed_reply') is True))
    queries={q['id']:q for q in read(HERE/'queries.json')}
    keys=[q+':'+m for q in queries for m in ('routed_graphrag','bm25','ms_basic','hybrid')]
    random.Random(20261012).shuffle(keys)
    aliases={k:f'A{i:03d}' for i,k in enumerate(keys,1)}
    packs=[];mapping=[];records=[]
    for key,cell in state['cells'].items():
        if cell['status'] not in {'complete','failed'}:continue
        # HTTP 200 alone means a visible response was returned. A context that
        # was merely assembled, or only attempted with an unknown outcome, is
        # not silently credited as material read by the answer model.
        actual=[]
        for event in state['events']:
            if event['cell']==key and event['service']=='generation' and http200(event):
                actual.append((event['sequence'],state['requests'][event['key']]['body']))
        for use in cell['uses']:
            if use['cache']:
                origin=state['events'][use['origin_event']-1]
                if origin['service']=='generation' and http200(origin):
                    pair=(origin['sequence'],state['requests'][use['key']]['body'])
                    if pair not in actual:actual.append(pair)
        exposure=[];sources=[];seen=set()
        for evidence in cell['evidence']:
            contexts=evidence['context'] if isinstance(evidence['context'],list) else [evidence['context']]
            for context in contexts:
                sequences=[seq for seq,body in actual if context and any(context in m['content'][0]['text'] for m in body['input'])]
                exposure.append({'evidence_key':evidence['evidence_key'],'context_sha256':text_sha(context),
                    'http200_generation_event_sequences':sequences,'source_ids':[s['short_id'] for s in evidence.get('sources',[])] if sequences else []})
                if sequences:
                    for source in evidence.get('sources',[]):
                        if source['text_unit_id'] not in seen:sources.append(source);seen.add(source['text_unit_id'])
        public={**cell,'actual_context_exposure':exposure,'raw_sources_in_http200_contexts':sources}
        file=f"cells/{cell['qid']}-{cell['method']}.json";write(OUT/file,public)
        answer=cell.get('answer') or ''
        packs.append({'anonymous_id':aliases[key],'question_id':cell['qid'],'query':queries[cell['qid']]['query'],
            'answer':answer,'answer_sha256':text_sha(answer),'status':'completed' if cell['status']=='complete' else 'failed'})
        mapping.append({'anonymous_id':aliases[key],'question_id':cell['qid'],'method':cell['method'],'cell_file':file})
        generations=[e for e in state['events'] if e['cell']==key and e['service']=='generation']
        known=[e['usage'] for e in generations if isinstance(e.get('usage'),dict)]
        records.append({'question_id':cell['qid'],'method':cell['method'],'route':cell['route'],'status':cell['status'],
            'failure':cell.get('failure'),'answer_sha256':text_sha(answer),'cell_file':file,
            'generation_input_tokens_reserved':cell['generation_input_tokens'],'elapsed_seconds':cell['elapsed_seconds'],
            'generation_reservations':len(generations),
            'known_provider_input_tokens':sum(u['prompt_tokens'] for u in known),
            'known_provider_output_tokens':sum(u['completion_tokens'] for u in known),
            'provider_usage_known_events':len(known),
            'provider_usage_unknown_possible_dispatch_events':sum(e.get('usage') is None and e.get('request_dispatched') is not False for e in generations),
            'reviewed_non_dispatch_reservations':sum(e['status']=='reviewed_non_dispatch' for e in generations),
            'cache_uses_without_new_physical_fee':sum(u['cache'] for u in cell['uses']),
            'raw_sources_in_http200_contexts':sources})
    for event in state['events']:
        seq=event['sequence'];request=read(RUN/f'request-{seq:02}.json')
        envelope=envelopes.get(seq)
        # Embedding weights are a cache, not needed for inspecting visible
        # inputs, charges or answer evidence. Retain their hash and shape only.
        if envelope and request['service']=='embedding' and 'response' in envelope:
            response=envelope['response'];rows=response.get('data',[])
            envelope={**envelope,'response':{'model':response.get('model'),'usage':response.get('usage'),
                'vectors_omitted':True,'vector_count':len(rows),'dimensions':[len(r.get('embedding',[])) for r in rows]},
                'private_complete_response_sha256':sha(RUN/f'response-{seq:02}.json')}
        write(OUT/f'wire/event-{seq:03d}.json',{'event':event,'request':request,'response_envelope':envelope})
    public={k:v for k,v in state.items() if k not in {'requests','cells','supervisor_pid'}}
    public.update(private_summary_sha256=hashlib.sha256(snapshot).hexdigest(),cells=records,
        export_state='partial' if partial else 'final',completion_counts=dict(Counter(c['status'] for c in state['cells'].values())),
        actual_http200_by_service=dict(Counter(e['service'] for e in state['events'] if http200(e))),
        note='Reservations are not successful calls. Unknown usage is null. No embedding vectors or credentials are exported.')
    write(OUT/'execution.json',public)
    random.Random(20261012).shuffle(packs)
    write(RUN/'blind-content-pack.json',{'rubric_sha256':sha(HERE/'answer-gold.json'),'rows':packs})
    write(RUN/'blind-method-map.json',mapping)
    write(OUT/'export-manifest.json',{'script_sha256':sha(Path(__file__)),'files':{str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*.json')) if p.name!='export-manifest.json'},'credential_reads':0,'api_calls':0})
    print(json.dumps({'exported_cells':len(records),'wire_events':len(state['events']),'state':state['status'],'api_calls':0}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    export(partial=args.partial)
