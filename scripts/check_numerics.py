"""Audit BLAS dot products against explicit contraction; no ranking tuning."""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import json,warnings
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from retrieval import ROOT,ranked,dump

torch.set_num_threads(4)
model=SentenceTransformer(str(ROOT/'.cache/model'),device='cpu',trust_remote_code=False)
queries=json.loads((ROOT/'benchmark/queries.json').read_text())
rows=[]
for q in queries:
    matrix=np.load(ROOT/'.cache/index'/q['repo']/'vectors.npy')
    v=model.encode([q['query']],normalize_embeddings=True,convert_to_numpy=True)[0]
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always')
        blas=matrix@v
    explicit=np.einsum('ij,j->i',matrix,v,optimize=False)
    reference=np.einsum('ij,j->i',matrix.astype(np.float64),v.astype(np.float64),optimize=False)
    rows.append(dict(query_id=q['id'],blas_finite=bool(np.isfinite(blas).all()),explicit_finite=bool(np.isfinite(explicit).all()),
        max_abs_blas_vs_reference=float(np.max(np.abs(blas-reference))),max_abs_explicit_vs_reference=float(np.max(np.abs(explicit-reference))),
        top12_equal=ranked(blas)[:12]==ranked(explicit)[:12],full_ranking_equal=ranked(blas)==ranked(explicit),
        warnings=[str(w.message) for w in ws]))
assert all(r['blas_finite'] and r['explicit_finite'] and r['top12_equal'] for r in rows)
dump(ROOT/'results/numerics.json',rows)
print('All 30 queries finite; top12 ranks equal; maximum BLAS absolute error versus float64:',max(r['max_abs_blas_vs_reference'] for r in rows))
