"""Model-free rankers for the future runner. Inputs are shared precomputed vectors.

This module does not load gold labels or contact embedding/generation endpoints.
A returned ranking is not a budgeted context: the future runner must serialize,
count and retain actual evidence within the protocol budget.
"""
from collections import Counter
import math
import re


def terms(text):
    # Keep full snake/camel identifiers and also their parts for code-aware BM25.
    words=re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[0-9]+', text)
    result=[]
    for word in words:
        result.append(word.lower())
        parts=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',word).replace('_',' ').lower().split()
        if parts != [word.lower()]:
            result.extend(parts)
    return result


def bm25(texts, query, k1=1.5, b=0.75):
    docs=[Counter(terms(text)) for text in texts]
    lengths=[sum(doc.values()) for doc in docs]
    avg=sum(lengths)/len(lengths) if lengths else 0
    freq=Counter(word for doc in docs for word in doc)
    scores=[]
    for doc,length in zip(docs,lengths):
        total=0.0
        for word in set(terms(query)):
            tf=doc[word]
            if not tf or not avg:
                continue
            idf=math.log(1+(len(docs)-freq[word]+0.5)/(freq[word]+0.5))
            total+=idf*tf*(k1+1)/(tf+k1*(1-b+b*length/avg))
        scores.append(total)
    return sorted(range(len(texts)),key=lambda i:(-scores[i],i))


def cosine(doc_vectors, query_vector):
    if not query_vector or not all(math.isfinite(x) for x in query_vector):
        raise ValueError('Invalid query vector')
    qnorm=math.sqrt(sum(x*x for x in query_vector))
    if qnorm==0:
        raise ValueError('Zero query vector')
    scores=[]
    for vector in doc_vectors:
        if len(vector)!=len(query_vector) or not all(math.isfinite(x) for x in vector):
            raise ValueError('Vector dimension/finite-value mismatch')
        norm=math.sqrt(sum(x*x for x in vector))
        if not norm:
            raise ValueError('Zero document vector')
        scores.append(sum(a*b for a,b in zip(vector,query_vector))/(norm*qnorm))
    return sorted(range(len(scores)),key=lambda i:(-scores[i],i))


def hybrid(texts,query,doc_vectors,query_vector,depth=20,rrf_k=60):
    if len(texts)!=len(doc_vectors):
        raise ValueError('Text/vector alignment mismatch')
    rankings=[bm25(texts,query)[:depth],cosine(doc_vectors,query_vector)[:depth]]
    scores=Counter()
    for ranking in rankings:
        for rank,index in enumerate(ranking,1):
            scores[index]+=1/(rrf_k+rank)
    return sorted(scores,key=lambda i:(-scores[i],i))
