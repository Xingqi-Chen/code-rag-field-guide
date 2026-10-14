"""Aggregate separately frozen evidence and citation judgments, without rescoring content."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent;OUT=HERE/'results'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def bound_hash(review, *names):
    values=[review[n] for n in names if n in review]
    assert values and len(set(values))==1, names
    return values[0]

def field(row, *names):
    present=[row[n] for n in names if n in row]
    assert present and all(v==present[0] for v in present), names
    return present[0]

def calculate():
    rubric=read(HERE/'answer-gold.json');required={x['id']:{c['id'] for c in x['criteria']} for x in rubric['items']}
    mapping={x['anonymous_id']:x for x in read(OUT/'grading-method-map.json')};rows=[];hashes={};seen=set()
    for batch in range(1,8):
        file=HERE/f'reviews/evidence-batch{batch}.json';review=read(file)
        assert 'in_progress' not in review.get('status','')
        assert not review.get('pending')
        content=HERE/f'reviews/content-batch{batch}.json'
        manifest=OUT/f'evidence-manifests/batch{batch}.json'
        assert bound_hash(review,'manifest_sha256','blind_evidence_manifest_sha256','evidence_manifest_sha256')==sha(manifest)
        assert bound_hash(review,'content_review_sha256','frozen_content_review_sha256')==sha(content)
        assert review['rubric_sha256']==sha(HERE/'answer-gold.json')
        expected={r['anonymous_id']:r for r in read(content)['rows']}
        assert len(review['rows'])==len(expected) and {r['anonymous_id'] for r in review['rows']}==set(expected)
        hashes[str(file.relative_to(HERE))]=sha(file)
        for row in review['rows']:
            aid=row['anonymous_id'];assert aid not in seen;seen.add(aid)
            assert row['question_id']==mapping[aid]['question_id']==expected[aid]['question_id']
            assert row['answer_sha256']==expected[aid]['answer_sha256']
            assert len(row['criteria'])==len(required[row['question_id']])
            assert {c['id'] for c in row['criteria']}==required[row['question_id']]
            assert all(type(c['evidence_score']) in (int,float) and c['evidence_score'] in {0,.5,1} for c in row['criteria'])
            mean=statistics.mean(c['evidence_score'] for c in row['criteria'])
            if 'evidence_mean' in row:assert math.isclose(mean,row['evidence_mean'])
            citations=field(row,'citations','citation_audit')
            missing=field(row,'missing_citation_claims','missing_citations')
            for citation in citations:
                assert all(citation[k] is None or type(citation[k]) is bool for k in ('resolves','location_match','supports'))
                assert citation['support_score'] is None or type(citation['support_score']) in (int,float) and citation['support_score'] in {0,.5,1}
                if citation['supports'] is True:assert citation['support_score']==1
            rows.append({'anonymous_id':aid,'question_id':row['question_id'],'method':mapping[aid]['method'],
                'evidence_score':mean,'citation_groups':len(citations),
                'resolvable_groups':sum(c['resolves'] is True for c in citations),
                'location_matching_groups':sum(c['location_match'] is True for c in citations),
                'fully_supporting_groups':sum(c['supports'] is True for c in citations),
                'partial_supporting_groups':sum(c['support_score']==.5 for c in citations),
                'missing_citation_claims':len(missing),
                'additional_error_records':len(row['additional_errors'])})
    assert len(rows)==92
    qs=rubric['question_sets'];cohorts={'main_test16':qs['main_test16_ids'],'main_dev4':qs['main_dev4_ids'],
        'main_all20_descriptive':qs['main20_ids'],'supplement6':qs['supplement6_ids']};aggregates=[]
    for cohort,ids in cohorts.items():
        for method in ('routed_graphrag','bm25','ms_basic','hybrid'):
            selected=[r for r in rows if r['method']==method and r['question_id'] in ids];assert len(selected)==len(ids)
            sums={k:sum(r[k] for r in selected) for k in ('citation_groups','resolvable_groups','location_matching_groups','fully_supporting_groups','partial_supporting_groups','missing_citation_claims','additional_error_records')}
            n=sums['citation_groups']
            aggregates.append({'cohort':cohort,'method':method,'questions':len(selected),
                'mean_criterion_evidence_score':statistics.mean(r['evidence_score'] for r in selected),**sums,
                'resolvable_fraction':sums['resolvable_groups']/n if n else None,
                'fully_supporting_fraction':sums['fully_supporting_groups']/n if n else None})
    return {'rubric_sha256':sha(HERE/'answer-gold.json'),'review_sha256':hashes,'rows':rows,'aggregates':aggregates,
        'interpretation':['Criterion evidence support is separate from content completion; missing answers may still have partial intermediate material.',
            'Citation unit is an annotated claim plus its citation group; segmentation and citation style differ, so fractions are descriptive, not an industry accuracy estimate.',
            'With a Source/graph record ID, support concerns that supplied unit and verifiable provenance; wrong fine line numbers are tracked separately as location mismatches.',
            'Missing citations are listed separately and do not enter the denominator of existing citation groups.',
            'No evidence/citation/content weighted composite is created. Overlapping supplemental questions reuse the same judgments.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args();value=calculate();file=OUT/'evidence-scores.json'
    if args.check:assert read(file)==value
    else:file.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(value['aggregates'],ensure_ascii=False,indent=2))
