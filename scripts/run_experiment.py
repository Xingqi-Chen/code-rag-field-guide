"""Run the frozen retrieval-only benchmark entirely on local CPU."""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
os.environ['OMP_NUM_THREADS']='4'
os.environ['MKL_NUM_THREADS']='4'
import hashlib
import importlib.metadata
import json
from pathlib import Path
import pickle
import platform
import resource
import statistics
import subprocess
import time
import torch
from sentence_transformers import SentenceTransformer
from retrieval import *


def timed(fn,n=3):
    elapsed=[]
    value=None
    for _ in range(n):
        t=time.perf_counter(); value=fn(); elapsed.append((time.perf_counter()-t)*1000)
    return value,statistics.median(elapsed)


def main():
    check_freeze()
    torch.set_num_threads(4)
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    torch.use_deterministic_algorithms(True)
    questions=json.loads((ROOT/'benchmark/queries.json').read_text())
    corpora=json.loads((ROOT/'benchmark/corpora.json').read_text())
    for repo in corpora:
        base=ROOT/'.cache/corpora'/repo['name']
        assert subprocess.check_output(['git','-C',str(base),'rev-parse','HEAD'],text=True).strip()==repo['commit']
        assert hashlib.sha256((base/repo['license_path']).read_bytes()).hexdigest()==repo['license_sha256']
        for q in [x for x in questions if x['repo']==repo['name']]:
            for e in q['evidence']:
                line=(base/e['path']).read_text().splitlines()[e['line']-1]
                assert hashlib.sha256(line.encode()).hexdigest()==e['line_sha256']
    start=time.perf_counter()
    model=SentenceTransformer(str(ROOT/'.cache/model'),device='cpu',trust_remote_code=False)
    model_load=time.perf_counter()-start
    assert model.max_seq_length>=240
    model.encode(['warm up local code retrieval'],normalize_embeddings=True)
    result_rows=[]; index_stats={}; all_meta=[]
    for repo in corpora:
        name=repo['name']
        print('BUILD',name,flush=True)
        chunks,adj,edges,stats=build(repo,model.tokenizer)
        t=time.perf_counter(); bm=BM25Okapi([tokens(c['text']) for c in chunks],k1=1.5,b=0.75)
        stats['bm25_seconds']=time.perf_counter()-t
        t=time.perf_counter()
        vectors=model.encode([c['text'] for c in chunks],batch_size=32,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
        stats['vector_seconds']=time.perf_counter()-t
        cache=ROOT/'.cache/index'/name;cache.mkdir(parents=True,exist_ok=True)
        dump(cache/'chunks.json',chunks);dump(cache/'edges.json',edges)
        (cache/'bm25.pkl').write_bytes(pickle.dumps(bm))
        np.save(cache/'vectors.npy',vectors)
        stats['bytes']={f.name:f.stat().st_size for f in sorted(cache.iterdir())}
        index_stats[name]=stats
        meta=[{k:v for k,v in c.items() if k!='text'} for c in chunks]
        all_meta.extend(meta)
        dump(ROOT/'results'/f'{name}-graph.json',dict(chunks=[c['id'] for c in chunks],edges=edges))
        print('INDEX',json.dumps(stats),flush=True)
        for q in [x for x in questions if x['repo']==name]:
            groups=relevance(q,chunks)
            bms,bm_ms=timed(lambda:bm.get_scores(tokens(q['query'])))
            # Include sorting in each corresponding retrieval phase.
            bo,bs_ms=timed(lambda:ranked(bms))
            query_vec,embed_ms=timed(lambda:model.encode([q['query']],normalize_embeddings=True,convert_to_numpy=True)[0])
            ds,dot_ms=timed(lambda:vectors@query_vec)
            do,ds_ms=timed(lambda:ranked(ds))
            ho,rrf_ms=timed(lambda:fuse(bo,do))
            stages={'bm25_ms':bm_ms+bs_ms,'embed_ms':embed_ms,'dense_search_ms':dot_ms+ds_ms,'fusion_ms':rrf_ms}
            for k in [4,8,12]:
                go,graph_ms=timed(lambda:expand(ho,adj,k,q['id']))
                ro,random_ms=timed(lambda:expand(ho,adj,k,q['id'],random=True))
                latency={'bm25':stages['bm25_ms'],'dense':embed_ms+stages['dense_search_ms']}
                latency['hybrid']=latency['bm25']+latency['dense']+rrf_ms
                latency['graph']=latency['hybrid']+graph_ms
                latency['random']=latency['hybrid']+random_ms
                for method,order in [('bm25',bo[:k]),('dense',do[:k]),('hybrid',ho[:k]),('graph',go),('random',ro)]:
                    assert len(order)==k and len(set(order))==k
                    row=dict(query_id=q['id'],repo=name,category=q['category'],method=method,k=k,
                        retrieved=[chunks[i]['id'] for i in order],relevant=sorted({chunks[i]['id'] for g in groups for i in g}),
                        evidence_groups=[[chunks[i]['id'] for i in sorted(g)] for g in groups],
                        metrics=metrics(order,groups,chunks),latency_ms=latency[method],
                        stages_ms=stages|{'graph_ms':graph_ms,'random_ms':random_ms},
                        top_bm25_score=float(bms[bo[0]]),top_dense_score=float(ds[do[0]]))
                    result_rows.append(row)
            print('RETRIEVED',q['id'],flush=True)
    dump(ROOT/'results/chunks.json',all_meta)
    (ROOT/'results/raw.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in result_rows))
    versions={p:importlib.metadata.version(p) for p in ['numpy','torch','transformers','sentence-transformers','rank-bm25','tokenizers']}
    env=dict(os=platform.system(),os_version=platform.mac_ver()[0],architecture=platform.machine(),python=platform.python_version(),
        processor='Apple M4',physical_memory_bytes=17179869184,logical_cpus=10,torch_threads=torch.get_num_threads(),device='cpu',
        seed=SEED,versions=versions,model='sentence-transformers/all-MiniLM-L6-v2',
        model_revision='1110a243fdf4706b3f48f1d95db1a4f5529b4d41',model_dimension=model.get_sentence_embedding_dimension(),
        model_max_seq_length=model.max_seq_length,model_load_seconds=model_load,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if platform.system()=='Darwin' else resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        source_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
        frozen_inputs=json.loads((ROOT/'benchmark/freeze.json').read_text()),index=index_stats)
    dump(ROOT/'results/environment.json',env)
    print('DONE',len(result_rows),'rows; peak RSS bytes',env['peak_rss_bytes'],flush=True)

if __name__=='__main__':main()
