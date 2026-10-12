"""Offline publication checks; reconstruct qrels independently of stored labels."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]

def main():
    freeze=json.loads((ROOT/'benchmark/freeze.json').read_text())
    for path,digest in freeze['files'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    qs={q['id']:q for q in json.loads((ROOT/'benchmark/queries.json').read_text())}
    assert len(qs)==30 and sum(not q['evidence'] for q in qs.values())==4
    chunks={c['id']:c for c in json.loads((ROOT/'results/chunks.json').read_text())}
    assert len(chunks)==1280
    for c in chunks.values():
        assert 0<c['tokens']<=240 and 1<=c['start']<=c['end']
        assert c['url'].startswith('https://github.com/')
    rows=[json.loads(x) for x in (ROOT/'results/raw.jsonl').read_text().splitlines()]
    keys={(r['query_id'],r['method'],r['k']) for r in rows}
    expected={(q,m,k) for q in qs for m in ['bm25','dense','hybrid','graph','random'] for k in [4,8,12]}
    assert keys==expected and len(rows)==len(expected)==450
    for r in rows:
        q=qs[r['query_id']]
        groups=[{cid for cid,c in chunks.items() if c['repo']==q['repo'] and c['path']==e['path'] and c['start']<=e['line']<=c['end']} for e in q['evidence']]
        assert all(groups) if groups else True
        assert groups==[set(g) for g in r['evidence_groups']],r['query_id']
        assert set(r['relevant'])==(set().union(*groups) if groups else set())
    for name in ['requests','click']:
        graph=json.loads((ROOT/'results'/f'{name}-graph.json').read_text())
        assert all(cid in chunks for cid in graph['chunks'])
        assert all(0<=a<b<len(graph['chunks']) and kind in {'static_call','same_symbol_next'} for a,b,kind in graph['edges'])
    subprocess.run([sys.executable,str(ROOT/'scripts/aggregate.py'),'--check'],check=True)
    files=subprocess.check_output(['git','-C',str(ROOT),'ls-files'],text=True).splitlines()
    for rel in files:
        p=ROOT/rel
        assert not rel.startswith(('.cache/','.venv/')),rel
        assert p.stat().st_size<5_000_000,rel
        s=p.read_text()
        assert not re.search(r'/(?:Users|home)/[A-Za-z0-9_-]+/',s),rel
        assert not re.search(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)',s),rel
        if p.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',s):
                if '://' in target or target.startswith('#') or target.startswith('mailto:'):continue
                target=target.split('#')[0]
                assert (p.parent/target).exists(),(rel,target)
    print('Validated freeze, 450 independent qrels, graph ranges, budgets via aggregation, tracked links, file sizes and publication privacy patterns.')
if __name__=='__main__':main()
