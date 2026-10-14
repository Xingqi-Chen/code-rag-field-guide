"""Prepare inspectable actual inputs only after content grades are frozen."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'strategy-routing';OUT=HERE/'results'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
    review=read(HERE/'content-review.json');pack=read(OUT/'blind-content-pack.json');execution=read(OUT/'execution.json')
    assert review['blind_pack_sha256']==sha(OUT/'blind-content-pack.json') and review['rubric_sha256']==sha(OLD/'answer-gold.json')
    assert {r['anonymous_id'] for r in review['rows']}=={r['anonymous_id'] for r in pack['rows']}
    cells={c['question_id']:c for c in execution['cells']};rows=[]
    for answer in pack['rows']:
        q=answer['question_id'];cell=read(OUT/cells[q]['cell_file']);calls=[]
        assert hashlib.sha256((cell.get('answer') or '').encode()).hexdigest()==answer['answer_sha256']
        for use in cell['uses']:
            if use.get('origin_run') and use['stage']=='hyde' and not calls:
                wire=read(OLD/f"results/wire/event-{use['origin_event']:03}.json")
                calls.append({'call_id':1,'origin':'inherited','stage':'hyde','request_body_sha256':wire['event']['request_body_sha256'],
                    'messages':wire['request']['body']['input'],'visible_response':wire['response_envelope'].get('response')})
        for event in execution['events']:
            if event['cell']!=q+':routed_graphrag' or event['service']!='generation':continue
            wire=read(OUT/f"wire/event-{event['sequence']:03}.json");env=wire['response_envelope']
            if env.get('http_status')!=200:continue
            calls.append({'call_id':len(calls)+1,'origin':'new','stage':event['stage'],'request_body_sha256':event['request_body_sha256'],
                'messages':wire['request']['body']['input'],'visible_response':env.get('response')})
        value={**answer,'calls_with_http200':calls,'raw_sources_in_supplied_contexts':cell['raw_sources_in_http200_contexts'],
            'instructions':'Content grading already frozen. Audit supplied material and citations separately. HyDE/intermediate claims are not source facts; do not credit undisclosed gold or entire graph as supplied. Graph index may be read only to trace citations/provenance.',
            'provenance_only_resources':{'graph':'research/pilot/results/code-prompt/index/','rubric':'research/pilot/strategy-routing/answer-gold.json'}}
        path=OUT/'evidence-packs'/f"{answer['anonymous_id']}.json";write(path,value);rows.append({'anonymous_id':answer['anonymous_id'],'question_id':q,'file':path.name,'sha256':sha(path)})
    write(OUT/'evidence-packs/manifest.json',{'rubric_sha256':sha(OLD/'answer-gold.json'),'content_review_sha256':sha(HERE/'content-review.json'),'rows':rows})
    print('Prepared six evidence packs; zero API calls.')
if __name__=='__main__':main()
