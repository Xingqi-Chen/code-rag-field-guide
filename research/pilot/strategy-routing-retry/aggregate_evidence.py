"""Six separate evidence reviews overlaid on the unchanged original 86."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import sys
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'strategy-routing';OUT=HERE/'results'
sys.path.insert(0,str(HERE))
from aggregate_results import validate_content_inputs
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def calculate():
    # Evidence review cannot silently bind incomplete or altered content grades.
    validate_content_inputs()
    review=read(HERE/'evidence-review.json');content=read(HERE/'content-review.json');rubric=read(OLD/'answer-gold.json')
    assert not review.get('pending') and not any(x in str(review.get('status','')).lower() for x in ('in_progress','pending','partial'))
    assert review['manifest_sha256']==sha(OUT/'evidence-packs/manifest.json') and review['content_review_sha256']==sha(HERE/'content-review.json') and review['rubric_sha256']==sha(OLD/'answer-gold.json')
    expected={r['anonymous_id']:r for r in content['rows']};required={q['id']:{c['id'] for c in q['criteria']} for q in rubric['items']};updates={}
    manifest=read(OUT/'evidence-packs/manifest.json')
    assert manifest['rubric_sha256']==review['rubric_sha256'] and manifest['content_review_sha256']==review['content_review_sha256']
    assert len(manifest['rows'])==6 and {r['anonymous_id'] for r in manifest['rows']}==set(expected)
    supplied_answers={}
    for entry in manifest['rows']:
        assert entry['file']==entry['anonymous_id']+'.json'
        path=OUT/'evidence-packs'/entry['file'];assert sha(path)==entry['sha256']
        supplied=read(path);p=expected[entry['anonymous_id']]
        assert entry['question_id']==p['question_id']
        assert all(supplied[k]==p[k] for k in ('anonymous_id','question_id','answer_sha256','status'))
        assert isinstance(supplied['answer'],str) and hashlib.sha256(supplied['answer'].encode()).hexdigest()==p['answer_sha256']
        supplied_answers[entry['anonymous_id']]=supplied['answer']
    assert len(review['rows'])==6 and {r['anonymous_id'] for r in review['rows']}==set(expected)
    for r in review['rows']:
        p=expected[r['anonymous_id']];q=r['question_id'];assert r['answer_sha256']==p['answer_sha256'] and q==p['question_id']
        assert q not in updates
        if 'status' in r:assert r['status']==p['status']
        assert {c['id'] for c in r['criteria']}==required[q] and len(r['criteria'])==len(required[q]);assert all(type(c['evidence_score']) in (int,float) and c['evidence_score'] in (0,.5,1) for c in r['criteria'])
        if 'evidence_mean' in r:
            assert type(r['evidence_mean']) in (int,float) and r['evidence_mean']==statistics.mean(c['evidence_score'] for c in r['criteria'])
        citations=r['citations']
        assert all(isinstance(r[k],list) for k in ('citations','missing_citation_claims','additional_errors'))
        for c in citations:
            assert isinstance(c['answer_quote'],str) and c['answer_quote'] and c['answer_quote'] in supplied_answers[r['anonymous_id']]
            assert isinstance(c['citation'],str) and c['citation'] and c['citation'] in supplied_answers[r['anonymous_id']]
            assert all(c[k] is None or type(c[k]) is bool for k in ('resolves','location_match','supports'))
            assert c['support_score'] is None or type(c['support_score']) in (int,float) and c['support_score'] in (0,.5,1)
            if c['supports'] is True:assert c['support_score']==1
        updates[q]={'anonymous_id':r['anonymous_id'],'question_id':q,'method':'routed_graphrag','evidence_score':statistics.mean(c['evidence_score'] for c in r['criteria']),
            'citation_groups':len(citations),'resolvable_groups':sum(c['resolves'] is True for c in citations),'location_matching_groups':sum(c['location_match'] is True for c in citations),
            'fully_supporting_groups':sum(c['supports'] is True for c in citations),'partial_supporting_groups':sum(c['support_score']==.5 for c in citations),
            'missing_citation_claims':len(r['missing_citation_claims']),'additional_error_records':len(r['additional_errors'])}
    original=read(OLD/'results/evidence-scores.json');rows=[updates[r['question_id']] if r['method']=='routed_graphrag' and r['question_id'] in updates else copy.deepcopy(r) for r in original['rows']]
    assert len(original['rows'])==92 and len({(r['question_id'],r['method']) for r in original['rows']})==92
    assert sum(r==o for r,o in zip(rows,original['rows']))==86
    qs=rubric['question_sets'];cohorts={'main_test16':qs['main_test16_ids'],'main_dev4':qs['main_dev4_ids'],'main_all20_descriptive':qs['main20_ids'],'supplement6':qs['supplement6_ids']};aggs=[]
    for cohort,ids in cohorts.items():
        for method in ('routed_graphrag','bm25','ms_basic','hybrid'):
            selected=[r for r in rows if r['method']==method and r['question_id'] in ids];assert len(selected)==len(ids)
            sums={k:sum(r[k] for r in selected) for k in ('citation_groups','resolvable_groups','location_matching_groups','fully_supporting_groups','partial_supporting_groups','missing_citation_claims','additional_error_records')};n=sums['citation_groups']
            aggs.append({'cohort':cohort,'method':method,'questions':len(selected),'mean_criterion_evidence_score':statistics.mean(r['evidence_score'] for r in selected),**sums,'resolvable_fraction':sums['resolvable_groups']/n if n else None,'fully_supporting_fraction':sums['fully_supporting_groups']/n if n else None})
    return {'original_evidence_scores_sha256':sha(OLD/'results/evidence-scores.json'),'retry_evidence_review_sha256':sha(HERE/'evidence-review.json'),'rows':rows,'aggregates':aggs,'interpretation':original['interpretation']+['Only the six retry cells are replaced; original judgments remain published unchanged.']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();x=calculate()
    if a.check:assert read(OUT/'evidence-scores.json')==x
    else:(OUT/'evidence-scores.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(x['aggregates'],indent=2))
