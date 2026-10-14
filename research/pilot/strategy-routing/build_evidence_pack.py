"""Prepare method-masked actual material for a second, separate evidence audit."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
RUN=ROOT/'.cache/pilot/strategy-routing-20261014';OUT=HERE/'results'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def main(batch):
    pack_path=RUN/f'blind-content-batch{batch}.json';pack=read(pack_path)
    review=HERE/f'reviews/content-batch{batch}.json'
    assert review.exists(),'Freeze content grading before exposing actual materials'
    graded=read(review);rubric=read(HERE/'answer-gold.json')
    assert graded['rubric_sha256']==pack['rubric_sha256']==sha(HERE/'answer-gold.json')
    assert graded['blind_pack_sha256']==sha(pack_path)
    expected={r['anonymous_id']:r for r in pack['rows']}
    assert all(hashlib.sha256(r['answer'].encode()).hexdigest()==r['answer_sha256'] for r in pack['rows'])
    assert len(expected)==len(pack['rows'])==len(graded['rows'])
    assert {r['anonymous_id'] for r in graded['rows']}==set(expected)
    required={r['id']:{c['id'] for c in r['criteria']} for r in rubric['items']}
    for row in graded['rows']:
        original=expected[row['anonymous_id']]
        assert row['question_id']==original['question_id'] and row['answer_sha256']==original['answer_sha256']
        assert row['status']==original['status']
        assert len(row['criteria'])==len(required[row['question_id']])
        assert {c['id'] for c in row['criteria']}==required[row['question_id']]
        assert all(type(c['score']) in (int,float) and c['score'] in {0,.5,1} for c in row['criteria'])
        assert math.isclose(row['content_mean'],statistics.mean(c['score'] for c in row['criteria']))
        if original['status']=='failed':assert row['content_mean']==0
    mapping={r['anonymous_id']:r for r in read(RUN/'blind-method-map.json')}
    state=read(OUT/'execution.json');events={e['sequence']:e for e in state['events']}
    rubrics={r['id']:r for r in read(HERE/'answer-gold.json')['items']}
    folder=RUN/f'blind-evidence-batch{batch}';rows=[]
    for row in pack['rows']:
        identity=row['anonymous_id'];cell=read(OUT/mapping[identity]['cell_file'])
        assert hashlib.sha256((cell.get('answer') or '').encode()).hexdigest()==row['answer_sha256']
        sequences=set()
        for e in state['events']:
            if e['cell']==cell['qid']+':'+cell['method'] and e['service']=='generation' and (e.get('http_status')==200 or e.get('recovered_completed_reply')):sequences.add(e['sequence'])
        sequences.update(u['origin_event'] for u in cell['uses'] if u['cache'] and events[u['origin_event']]['service']=='generation')
        calls=[]
        for seq in sorted(sequences):
            wire=read(OUT/f'wire/event-{seq:03d}.json')
            if (wire.get('response_envelope') or {}).get('http_status')!=200:continue
            calls.append({'call_id':len(calls)+1,'messages':wire['request']['body']['input'],
                'visible_response':wire['response_envelope']['response'],
                'request_body_sha256':wire['event']['request_body_sha256']})
        overlap=[]
        for evidence in rubrics[row['question_id']]['evidence']:
            wanted=set(range(evidence['start_line'],evidence['end_line']+1));covered=set()
            for s in cell['raw_sources_in_http200_contexts']:
                if s['path']==evidence['path']:covered.update(range(s['start_line'],s['end_line']+1))
            overlap.append({'anchor_id':evidence['id'],'path':evidence['path'],'start_line':evidence['start_line'],
                'end_line':evidence['end_line'],'raw_source_line_coverage':len(wanted&covered)/len(wanted)})
        value={**row,'calls_with_http200':calls,'raw_sources_in_supplied_contexts':cell['raw_sources_in_http200_contexts'],
            'gold_anchor_raw_overlap_diagnostic':overlap,
            'instructions':'Content scores already frozen. Raw overlap is a navigation diagnostic, not an automatic evidence grade. Summaries/entities/relationships may support a point through a verifiable provenance chain. Audit exact claims, citations, and actual messages; do not credit hidden gold as supplied evidence.',
            'provenance_only_resources':{'graph':'research/pilot/results/code-prompt/index/','note':'These full index records are for tracing citations to sources; their existence does not imply the answer model received them.'}}
        file=folder/f'{identity}.json';write(file,value)
        rows.append({'anonymous_id':identity,'question_id':row['question_id'],'file':file.name,'sha256':sha(file)})
    manifest={'content_pack_sha256':sha(pack_path),'frozen_content_review_sha256':sha(review),'rubric_sha256':pack['rubric_sha256'],
        'scope':'Second-stage evidence/citation audit, content grades already frozen; no method labels supplied.', 'rows':rows}
    write(folder/'manifest.json',manifest);print(json.dumps({'batch':batch,'cases':len(rows),'manifest_sha256':sha(folder/'manifest.json'),'api_calls':0}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('batch',type=int);main(p.parse_args().batch)
