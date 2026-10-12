"""Recompute metrics from published ranks+anchors. Standard library only."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import statistics

ROOT=Path(__file__).resolve().parents[1]
METRICS=['recall','mrr','ndcg','evidence_coverage','all_evidence','unlabelled_fraction','context_tokens','latency_ms']

def recompute(row,meta):
    order=row['retrieved']; rel=set(row['relevant']);groups=row['evidence_groups']
    hits=[int(x in rel) for x in order]
    context=sum(meta[x]['tokens'] for x in order)
    if not groups:
        return dict(recall=None,mrr=None,ndcg=None,evidence_coverage=None,all_evidence=None,unlabelled_fraction=1.0,context_tokens=context)
    dcg=sum(h/math.log2(i+2) for i,h in enumerate(hits))
    ideal=sum(1/math.log2(i+2) for i in range(min(len(rel),len(order))))
    covered=sum(bool(set(order)&set(g)) for g in groups)
    return dict(recall=sum(hits)/len(rel),mrr=next((1/(i+1) for i,h in enumerate(hits) if h),0),ndcg=dcg/ideal,
        evidence_coverage=covered/len(groups),all_evidence=int(covered==len(groups)),unlabelled_fraction=1-sum(hits)/len(order),context_tokens=context)

def avg(rows):
    return {'n':len(rows)}|{m:statistics.mean(r['latency_ms'] if m=='latency_ms' else r['metrics'][m] for r in rows) for m in METRICS}

def aggregate(rows,meta):
    for r in rows:
        assert len(r['retrieved'])==r['k'] and len(set(r['retrieved']))==r['k']
        assert all(meta[x]['repo']==r['repo'] for x in r['retrieved'])
        assert sum(meta[x]['tokens'] for x in r['retrieved'])<=240*r['k']
        for key,v in recompute(r,meta).items():
            actual=r['metrics'][key]
            assert (v is None and actual is None) or (v is not None and abs(v-actual)<1e-10),(r['query_id'],key,v,actual)
    positive=[r for r in rows if r['evidence_groups']]
    grouped=defaultdict(list)
    for r in positive:
        for scope in ['all','repo:'+r['repo'],'category:'+r['category']]:
            grouped[(scope,r['k'],r['method'])].append(r)
    summary=[dict(scope=s,k=k,method=m,**avg(rs)) for (s,k,m),rs in sorted(grouped.items())]
    at8={(r['query_id'],r['method']):r for r in positive if r['k']==8}
    pairs=[]
    for q in sorted({qid for qid,_ in at8}):
        g=at8[q,'graph'];h=at8[q,'hybrid']
        pairs.append(dict(query_id=q,repo=g['repo'],category=g['category'],hybrid=h['metrics']['evidence_coverage'],
            graph=g['metrics']['evidence_coverage'],delta=g['metrics']['evidence_coverage']-h['metrics']['evidence_coverage']))
    deltas=[p['delta'] for p in pairs]
    rng=random.Random(1729)
    boots=sorted(statistics.mean(rng.choices(deltas,k=len(deltas))) for _ in range(10000))
    interval=dict(mean=statistics.mean(deltas),bootstrap_percentile95=[boots[249],boots[9749]],resamples=10000,
        wins=sum(x>0 for x in deltas),ties=sum(x==0 for x in deltas),losses=sum(x<0 for x in deltas))
    negatives=[dict(query_id=r['query_id'],method=r['method'],returned=len(r['retrieved']),top_bm25_score=r['top_bm25_score'],top_dense_score=r['top_dense_score']) for r in rows if not r['evidence_groups'] and r['k']==8]
    return dict(groups=summary,paired_graph_minus_hybrid_at8=interval,pairs_at8=pairs,negatives_at8=negatives)

def markdown(result):
    out=['# 可复算检索结果','', '仅26个正例进入均值；4个负例见原始结果。下表由 `python3 scripts/aggregate.py` 自动生成。', '',
        '|预算|方法|Recall|MRR|nDCG|证据覆盖|全部证据命中|未标注块比例|平均token|平均阶段合计ms|',
        '|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in result['groups']:
        if r['scope']!='all':continue
        out.append(f"|{r['k']}|{r['method']}|{r['recall']:.3f}|{r['mrr']:.3f}|{r['ndcg']:.3f}|{r['evidence_coverage']:.3f}|{r['all_evidence']:.3f}|{r['unlabelled_fraction']:.3f}|{r['context_tokens']:.1f}|{r['latency_ms']:.2f}|")
    out += ['', '## 主预算分组证据覆盖', '', '|范围|方法|题数|覆盖率|','|---|---|---:|---:|']
    for r in result['groups']:
        if r['scope']=='all' or r['k']!=8:continue
        out.append(f"|{r['scope']}|{r['method']}|{r['n']}|{r['evidence_coverage']:.3f}|")
    p=result['paired_graph_minus_hybrid_at8']
    out += ['',f"图减hybrid，平均差 {p['mean']:.4f}；配对bootstrap描述区间 {p['bootstrap_percentile95']}；胜/平/负 {p['wins']}/{p['ties']}/{p['losses']}。此区间不代表随机抽样总体。", '',
        '## 逐题图与混合检索比较', '', '|题目|类型|Hybrid覆盖|Graph覆盖|差值|','|---|---|---:|---:|---:|']
    for r in result['pairs_at8']:
        out.append(f"|{r['query_id']}|{r['category']}|{r['hybrid']:.3f}|{r['graph']:.3f}|{r['delta']:+.3f}|")
    return '\n'.join(out)+'\n'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');a=parser.parse_args()
    rows=[json.loads(x) for x in (ROOT/'results/raw.jsonl').read_text().splitlines()]
    meta={r['id']:r for r in json.loads((ROOT/'results/chunks.json').read_text())}
    result=aggregate(rows,meta)
    js=json.dumps(result,ensure_ascii=False,indent=2)+'\n';md=markdown(result)
    for filename,content in [('summary.json',js),('summary.md',md)]:
        path=ROOT/'results'/filename
        if a.check: assert path.read_text()==content,filename
        else:path.write_text(content)
    print('Verified',len(rows),'rankings; metrics recomputed from evidence groups and chunk metadata.')
    print(json.dumps(result['paired_graph_minus_hybrid_at8']))
if __name__=='__main__':main()
