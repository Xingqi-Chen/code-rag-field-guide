"""Deterministic static Python indexing and retrieval, no corpus imports/execution."""
from __future__ import annotations
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import time
import numpy as np
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
SEED = 1729
STOP = set('a an the and or of to in for from with is are be can does do how where what which when why into its it this that as at by if then than on no not'.split())


def tokens(s):
    words = re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[0-9]+', s)
    out = []
    for w in words:
        parts = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', w).replace('_', ' ').lower().split()
        pieces = [w.lower()] + (parts if parts != [w.lower()] else [])
        out.extend(x for x in pieces if x not in STOP)
    return out


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def check_freeze():
    frozen = json.loads((ROOT/'benchmark/freeze.json').read_text())
    for name, digest in frozen['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name


def build(repo, tokenizer):
    """Partition by deepest AST definition; connect call-site chunks to definitions."""
    tokenizer.deprecation_warnings['sequence-length-is-longer-than-the-specified-maximum'] = True
    start = time.perf_counter()
    base = ROOT/'.cache/corpora'/repo['name']
    chunks, symbols, modules, file_data = [], {}, {}, {}
    oversized = 0
    for path in sorted((base/repo['source']).rglob('*.py')):
        rel = path.relative_to(base).as_posix()
        mod = rel.removeprefix('src/').removesuffix('.py').replace('/', '.')
        if mod.endswith('.__init__'):
            mod = mod[:-9]
        text = path.read_text()
        lines = text.splitlines(keepends=True)
        tree = ast.parse(text)
        entries = []
        module_id = mod + ':<module>@1'
        symbols[module_id] = dict(id=module_id, module=mod, qual='<module>', kind='module', cls=None, node=tree)
        owner = [module_id] * len(lines)

        def visit(node, scope='', cls=None):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qual = scope + child.name
                    sid = f'{mod}:{qual}@{child.lineno}'
                    kind = 'class' if isinstance(child, ast.ClassDef) else 'function'
                    symbols[sid] = dict(id=sid, module=mod, qual=qual, kind=kind, cls=cls, node=child)
                    a = min([child.lineno] + [d.lineno for d in child.decorator_list])
                    for i in range(a-1, child.end_lineno):
                        owner[i] = sid
                    entries.append(sid)
                    visit(child, qual+'.', qual if kind == 'class' else cls)
                else:
                    visit(child, scope, cls)
        visit(tree)
        imports = {}
        package = mod if path.name == '__init__.py' else mod.rsplit('.', 1)[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
            elif isinstance(node, ast.ImportFrom):
                prefix = package.split('.')
                if node.level:
                    prefix = prefix[:len(prefix)-node.level+1]
                    target = '.'.join(prefix + ([node.module] if node.module else []))
                else:
                    target = node.module or ''
                for alias in node.names:
                    if alias.name != '*':
                        imports[alias.asname or alias.name] = target+'.'+alias.name
        modules[mod] = {'imports': imports, 'entries': entries}
        file_data[rel] = {'tree': tree, 'owner': owner, 'module': mod, 'lines': len(lines)}
        # Preserve all non-empty lines; no overlap and no enclosing class duplication.
        i = 0
        while i < len(lines):
            sid = owner[i]
            sym = symbols[sid]
            prefix = f'{rel} {sym["qual"]}\n'
            j, body = i, ''
            while j < len(lines) and owner[j] == sid:
                candidate = body + lines[j]
                if len(tokenizer.encode(prefix+candidate, add_special_tokens=True)) > 240:
                    break
                body = candidate
                j += 1
            if j == i:
                # Rare long source line: slice by tokenizer offsets. Kept separate,
                # any anchor on such a line requires all fragments (evaluation).
                oversized += 1
                encoded = tokenizer(lines[i], add_special_tokens=False, return_offsets_mapping=True)
                offsets = encoded['offset_mapping']
                capacity = 240-len(tokenizer.encode(prefix, add_special_tokens=True))-2
                for part, at in enumerate(range(0, len(offsets), capacity)):
                    a, b = offsets[at][0], offsets[min(at+capacity,len(offsets))-1][1]
                    add_chunk(chunks,repo,rel,sid,i+1,i+1,prefix+lines[i][a:b],tokenizer,part)
                i += 1
            else:
                if body.strip():
                    add_chunk(chunks,repo,rel,sid,i+1,j,prefix+body,tokenizer,0)
                i = j
    partition_seconds = time.perf_counter()-start
    start = time.perf_counter()
    by_symbol, by_path = defaultdict(list), defaultdict(list)
    for n,c in enumerate(chunks):
        by_symbol[c['symbol']].append(n)
        by_path[c['path']].append(n)
    lookup = {}
    for sid,s in symbols.items():
        lookup[s['module']+'.'+s['qual']] = sid
    edges = set()
    def edge(a,b,kind):
        if a != b:
            edges.add((min(a,b),max(a,b),kind))
    for ids in by_symbol.values():
        for a,b in zip(ids,ids[1:]):
            edge(a,b,'same_symbol_next')

    def resolve(expr, mod, cls=None, seen=None):
        if isinstance(expr, ast.Name):
            name = modules[mod]['imports'].get(expr.id, mod+'.'+expr.id)
            return name
        if isinstance(expr, ast.Attribute):
            if isinstance(expr.value, ast.Name) and expr.value.id in {'self','cls'} and cls:
                direct = mod+'.'+cls+'.'+expr.attr
                if direct in lookup:
                    return direct
                seen = set() if seen is None else seen
                ck = mod+'.'+cls
                if ck in seen:
                    return None
                seen.add(ck)
                cs = symbols.get(lookup.get(ck,''))
                if cs and isinstance(cs['node'],ast.ClassDef):
                    for base_expr in cs['node'].bases:
                        b = resolve(base_expr,mod)
                        bs = symbols.get(lookup.get(b,''))
                        if bs:
                            r = resolve(expr,bs['module'],bs['qual'],seen)
                            if r:
                                return r
                return None
            value = resolve(expr.value,mod,cls)
            return value+'.'+expr.attr if value else None
        return None

    total_calls, resolved_calls = 0, 0
    for rel,data in file_data.items():
        for node in ast.walk(data['tree']):
            if not isinstance(node,ast.Call):
                continue
            total_calls += 1
            owner = symbols[data['owner'][node.lineno-1]]
            cls = owner['cls']
            name = resolve(node.func,data['module'],cls)
            sid = lookup.get(name)
            if sid and symbols[sid]['kind'] == 'class':
                sid = lookup.get(name+'.__init__', sid)
            if not sid or not by_symbol[sid]:
                continue
            source = next((i for i in by_path[rel] if chunks[i]['start']<=node.lineno<=chunks[i]['end']),None)
            if source is not None:
                edge(source,by_symbol[sid][0],'static_call')
                resolved_calls += 1
    adjacency = [set() for _ in chunks]
    for a,b,_ in edges:
        adjacency[a].add(b); adjacency[b].add(a)
    graph_seconds = time.perf_counter()-start
    return chunks, adjacency, sorted(edges), dict(files=len(file_data),lines=sum(d['lines'] for d in file_data.values()),
        chunks=len(chunks),symbols=len(symbols),oversized_lines=oversized,calls_seen=total_calls,calls_resolved=resolved_calls,
        edges=len(edges),static_call_edges=sum(k=='static_call' for _,_,k in edges),
        same_symbol_edges=sum(k=='same_symbol_next' for _,_,k in edges),
        isolated_chunks=sum(not x for x in adjacency),partition_seconds=partition_seconds,graph_seconds=graph_seconds)


def add_chunk(chunks,repo,rel,sid,a,b,text,tokenizer,part):
    count=len(tokenizer.encode(text,add_special_tokens=True))
    assert count <= 240, (rel,a,count)
    chunks.append(dict(id=f'{repo["name"]}/{rel}:{a}-{b}:{part}',repo=repo['name'],path=rel,symbol=sid,
        start=a,end=b,part=part,tokens=count,text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        url=f'{repo["url"]}/blob/{repo["commit"]}/{rel}#L{a}-L{b}'))


def ranked(scores):
    return np.argsort(-np.asarray(scores),kind='stable').tolist()


def fuse(bm_order,dense_order):
    score=np.zeros(len(bm_order),dtype=np.float64)
    for order in [bm_order,dense_order]:
        for rank,idx in enumerate(order,1):
            score[idx]+=1/(60+rank)
    return ranked(score)


def expand(order,adjacency,k,query_id,random=False):
    seeds=order[:k//2]
    pos={x:i for i,x in enumerate(order)}
    if random:
        rng=np.random.default_rng(SEED+int(hashlib.sha256(query_id.encode()).hexdigest()[:8],16))
        available=[x for x in order if x not in seeds]
        candidates=rng.choice(available,min(k-len(seeds),len(available)),replace=False).tolist()
    else:
        candidates=list(set().union(*(adjacency[x] for x in seeds))-set(seeds))
    selected=seeds+sorted(candidates,key=lambda x:pos[x])[:k-len(seeds)]
    selected+= [x for x in order if x not in selected][:k-len(selected)]
    return selected


def relevance(question,chunks):
    # Evidence anchors were frozen independently of chunks/ranking.
    groups=[]
    for e in question['evidence']:
        ids={i for i,c in enumerate(chunks) if c['path']==e['path'] and c['start']<=e['line']<=c['end']}
        assert ids, (question['id'],e)
        groups.append(ids)
    return groups


def metrics(order,groups,chunks):
    if not groups:
        return dict(recall=None,mrr=None,ndcg=None,evidence_coverage=None,all_evidence=None,
            unlabelled_fraction=1.0,context_tokens=sum(chunks[x]['tokens'] for x in order))
    relevant=set().union(*groups)
    hits=[int(x in relevant) for x in order]
    dcg=sum(h/np.log2(i+2) for i,h in enumerate(hits))
    ideal=sum(1/np.log2(i+2) for i in range(min(len(relevant),len(order))))
    found=sum(bool(set(order)&g) for g in groups)
    return dict(recall=sum(hits)/len(relevant),mrr=next((1/(i+1) for i,h in enumerate(hits) if h),0),
        ndcg=float(dcg/ideal),evidence_coverage=found/len(groups),all_evidence=int(found==len(groups)),
        unlabelled_fraction=1-sum(hits)/len(order),context_tokens=sum(chunks[x]['tokens'] for x in order))
