"""Offline verification and aggregation; no model, tokenizer or private cache needed.

Rubric judgements are published independent AI review annotations, not computed
truth. This script only checks their alignment and recomputes arithmetic/usage.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

PILOT=Path(__file__).resolve().parent
ROOT=PILOT.parents[1]
OUT=PILOT/'results/global'

def read(p):return json.loads(p.read_text())
def sha(b):return hashlib.sha256(b).hexdigest()


def verify(require_reviews=True,tokens=False):
    plan=read(PILOT/'global-plan.json')
    questions=read(PILOT/'global-questions.json')
    gold={q['id']:q for q in read(PILOT/'global-gold.json')['items']}
    preflight=read(OUT/'preflight.json')
    for rel,digest in preflight['hashes'].items():
        if not rel.startswith('.cache/'):
            assert sha((ROOT/rel).read_bytes())==digest,rel
    for qid,digest in preflight['baseline_context_sha256'].items():
        assert sha((OUT/'contexts'/f'{qid}-bm25.json').read_bytes())==digest
    assert sha((OUT/'map-contexts.json').read_bytes())==preflight['map_context_sha256']
    assert len(questions)==6 and set(gold)=={q['id'] for q in questions}
    execution=read(OUT/'execution.json');events=execution['events']
    assert execution['status']=='complete' and execution['original_inputs_unchanged']
    assert execution['automatic_retries']==0 and execution['embedding_calls']==0 and not execution['index_rebuilt']
    assert 48<=len(events)<=54<=plan['limits']['physical_generation_attempts']
    assert execution['elapsed_seconds']<=3600
    assert len({e['request_body_sha256'] for e in events})==len(events)
    assert execution['input_content_tokens']==sum(e['input_content_tokens'] for e in events)<=864000
    calls={}
    encoder=None
    if tokens:
        import probe_runtime
        encoder,_=probe_runtime.tokenizers()
        chunks=read(OUT/'map-contexts.json')['chunks']
        assert [len(encoder.encode(s)) for s in chunks]==preflight['map_context_tokens']
    for i,e in enumerate(events,1):
        assert e['sequence']==i and e['status']=='validated' and e['http_status']==200
        assert 0<e['input_content_tokens']<=16000
        c=read(OUT/'calls'/f'{i:02}.json');calls[i]=c
        assert c['event']==e and c['usage']==e['usage'] and c['model']==plan['model']
        assert e['usage']['total_tokens']==e['usage']['prompt_tokens']+e['usage']['completion_tokens']
        body={'model':plan['model'],'input':[{'role':m['role'],'content':[{
            'type':'output_text' if m['role']=='assistant' else 'input_text','text':m['content']}]} for m in c['messages']],
            'max_output_tokens':2048,'store':False,'stream':True,'num_retries':0,'fallbacks':[],
            'context_window_fallback_dict':{},'caching':False}
        canonical=json.dumps(body,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        assert sha(canonical.encode())==e['request_body_sha256']
        if encoder:
            assert sum(len(encoder.encode(m['content'])) for m in c['messages'])==e['input_content_tokens']
            assert len(encoder.encode(c['response']))==e['visible_output_tokens']
    report_ids={str(r['id']) for r in read(OUT/'map-contexts.json')['records']['reports']}
    rows=[]
    for q in questions:
        for method in ['global','bm25']:
            a=read(OUT/'answers'/f'{q["id"]}-{method}.json')
            es=[e for e in events if e['question_id']==q['id'] and e['method']==method]
            assert a['call_sequences']==[e['sequence'] for e in es]
            assert len(es)==(1 if method=='bm25' else 7+sum(e['stage']=='reduce' for e in es))
            if method=='global':
                assert sum(e['stage']=='map' for e in es)==7 and len(a['map_points'])==7
                assert a['source_excerpts_provided']==0
                if encoder:assert len(encoder.encode(a['reduce_context']))==a['reduce_context_tokens']
            elif encoder:
                context=read(OUT/'contexts'/f'{q["id"]}-bm25.json')
                assert len(encoder.encode(context['context']))==context['context_tokens']<=12000
            last=es[-1]
            if last['stage'] in ('reduce','answer'):assert a['answer']==calls[last['sequence']]['response']
            user_messages=[c['content'] for e in es for c in calls[e['sequence']]['messages'] if c['role']=='user']
            assert all(s.startswith(q['query']+'\n\n') for s in user_messages)
            ids=[]
            if method=='global':
                for group in re.findall(r'Reports\s*\(([^)]*)\)',a['answer']):
                    ids += re.findall(r'\b\d+\b',group)
            rows.append({'question_id':q['id'],'group':q['group'],'method':method,
                'calls':len(es),'map_calls':sum(e['stage']=='map' for e in es),
                'reduce_calls':sum(e['stage']=='reduce' for e in es),
                'provider_input_tokens':sum(e['usage']['prompt_tokens'] for e in es),
                'provider_output_tokens':sum(e['usage']['completion_tokens'] for e in es),
                'visible_output_tokens_all_calls':sum(e['visible_output_tokens'] for e in es),
                'input_content_tokens':sum(e['input_content_tokens'] for e in es),
                'request_seconds':sum(e['elapsed_seconds'] for e in es),
                'elapsed_seconds':a['elapsed_seconds'],
                'over_requested_output_cap_calls':sum(e['requested_output_limit_exceeded'] for e in es),
                'cited_report_ids':sorted(set(ids),key=int),
                'unknown_cited_report_ids':sorted(set(ids)-report_ids,key=int)})
    # Both arms receive exactly the same question and common instruction.
    for q in questions:
        us=[]
        for method in ['global','bm25']:
            e=next(e for e in events if e['question_id']==q['id'] and e['method']==method)
            us.append([m['content'] for m in calls[e['sequence']]['messages'] if m['role']=='user'])
        assert us[0]==us[1]
    reviews=[]
    if require_reviews:
        for filename in ['review-precise.json','review-global.json']:
            reviews+=read(OUT/filename)['assessments']
        assert len(reviews)==12 and len({(r['question_id'],r['method']) for r in reviews})==12
        lookup={(r['question_id'],r['method']):r for r in reviews}
        for row in rows:
            r=lookup[(row['question_id'],row['method'])]
            assert [x['id'] for x in r['criteria']]==[x['id'] for x in gold[row['question_id']]['criteria']]
            assert all(x['score'] in [0,0.5,1] and x['rationale'] for x in r['criteria'])
            row['criterion_points']=sum(x['score'] for x in r['criteria'])
            row['criterion_max']=len(r['criteria'])
            row['criterion_coverage']=row['criterion_points']/row['criterion_max']
            row['factual_errors']=len(r['factual_errors'])
            row['unsupported_assertions']=len(r['unsupported_assertions'])
    groups=[]
    for group in ['precise','global']:
        for method in ['global','bm25']:
            selected=[r for r in rows if r['group']==group and r['method']==method]
            group_row={'group':group,'method':method,'questions':len(selected)}
            for metric in ['calls','map_calls','reduce_calls','provider_input_tokens','provider_output_tokens',
                           'request_seconds','over_requested_output_cap_calls']:
                group_row[metric]=sum(r[metric] for r in selected)
            if require_reviews:
                group_row['criterion_coverage_macro']=sum(r['criterion_coverage'] for r in selected)/len(selected)
                group_row['criterion_points']=sum(r['criterion_points'] for r in selected)
                group_row['criterion_max']=sum(r['criterion_max'] for r in selected)
            groups.append(group_row)
    stages=[]
    for stage in ['map','reduce','answer']:
        selected=[e for e in events if e['stage']==stage]
        stages.append({'stage':stage,'calls':len(selected),
            'provider_input_tokens':sum(e['usage']['prompt_tokens'] for e in selected),
            'provider_output_tokens':sum(e['usage']['completion_tokens'] for e in selected),
            'request_seconds':sum(e['elapsed_seconds'] for e in selected)})
    return {'schema':1,'status':execution['status'],'physical_generation_calls':len(events),
        'embedding_calls':0,'index_rebuilt':False,'elapsed_seconds':execution['elapsed_seconds'],
        'provider_input_tokens':sum(e['usage']['prompt_tokens'] for e in events),
        'provider_output_tokens':sum(e['usage']['completion_tokens'] for e in events),
        'rows':rows,'groups':groups,'stages':stages,
        'review_sha256':{name:sha((OUT/name).read_bytes()) for name in
            ['review-precise.json','review-global.json']} if require_reviews else {},
        'interpretation':'Exploratory six-question answer review, purposive selection, independent AI annotations; not human ground truth or retrieval Recall. Global and BM25 use different total compute and prompts. Report IDs alone do not prove source-level support.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--before-review',action='store_true')
    p.add_argument('--tokens',action='store_true')
    args=p.parse_args();result=verify(not args.before_review,args.tokens)
    if args.check:assert read(OUT/'scores.json')==result,'global summary changed'
    elif not args.before_review:(OUT/'scores.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','physical_generation_calls','provider_input_tokens','provider_output_tokens']}))
