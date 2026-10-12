"""Offline publication checks; reconstruct qrels independently of stored labels."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import struct
import xml.etree.ElementTree as ET
import zlib
ROOT=Path(__file__).resolve().parents[1]

def check_png(data):
    """Accept our RGB PNGs with no metadata, trailing payload or broken CRCs."""
    assert data[:8]==b'\x89PNG\r\n\x1a\n','PNG signature'
    offset=8; kinds=[]; dimensions=None; ended=False
    while offset<len(data):
        assert offset+12<=len(data),'PNG truncated chunk'
        size=struct.unpack('>I',data[offset:offset+4])[0]
        kind=data[offset+4:offset+8]; end=offset+12+size
        assert end<=len(data),'PNG truncated data'
        payload=data[offset+8:end-4]
        assert kind in {b'IHDR',b'IDAT',b'IEND'},'PNG metadata or unexpected chunk'
        assert zlib.crc32(kind+payload)&0xffffffff==struct.unpack('>I',data[end-4:end])[0],'PNG CRC'
        if kind==b'IHDR':
            assert not kinds and size==13,'PNG header order'
            width,height,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',payload)
            assert width==1520 and 1<=height<=3000,'PNG dimensions'
            assert (depth,color,compression,filtering,interlace)==(8,2,0,0,0),'PNG RGB format'
            dimensions=(width,height)
        if kind==b'IEND':
            assert size==0 and end==len(data),'PNG trailing data'
            ended=True
        kinds.append(kind); offset=end
    assert ended and kinds[0]==b'IHDR' and kinds[-1]==b'IEND' and b'IDAT' in kinds,'PNG incomplete'
    return dimensions

def check_svg(text):
    """Validate the small, self-contained vocabulary emitted by our generator."""
    assert '<!DOCTYPE' not in text and '<!ENTITY' not in text,'SVG entities'
    root=ET.fromstring(text); ns='{http://www.w3.org/2000/svg}'
    assert root.tag==ns+'svg' and root.attrib.get('role')=='img','SVG root'
    allowed={'svg','title','desc','rect','text','line','polygon'}
    for item in root.iter():
        assert item.tag in {ns+x for x in allowed},'SVG unsupported element'
        assert all(not k.lower().startswith('on') and 'href' not in k.lower() for k in item.attrib),'SVG active attribute'
        assert all('url(' not in v.lower() for v in item.attrib.values()),'SVG external resource'
    for tag in ['title','desc']:
        item=root.find(ns+tag)
        assert item is not None and item.text and item.text.strip(),('SVG accessibility',tag)
    assert root.attrib.get('aria-labelledby')=='title desc','SVG accessibility IDs'
    assert root.find(ns+'title').attrib.get('id')=='title'
    assert root.find(ns+'desc').attrib.get('id')=='desc'
    width,height=int(root.attrib['width']),int(root.attrib['height'])
    assert width==760 and 1<=height<=1500,'SVG dimensions'
    assert root.attrib['viewBox']==f'0 0 {width} {height}','SVG viewBox'
    return width,height

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
    files=subprocess.check_output(['git','-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard'],text=True).splitlines()
    for rel in files:
        p=ROOT/rel
        assert not rel.startswith(('.cache/','.venv/')),rel
        assert p.stat().st_size<5_000_000,rel
        if p.suffix=='.png':
            width,height=check_png(p.read_bytes())
            assert p.with_suffix('.svg').exists(),rel
            sw,sh=check_svg(p.with_suffix('.svg').read_text())
            assert (width,height)==(sw*2,sh*2),rel
            continue
        s=p.read_text()
        if p.suffix=='.svg':
            check_svg(s)
            assert p.with_suffix('.png').exists(),rel
        assert not re.search(r'/(?:Users|home)/[A-Za-z0-9_-]+/',s),rel
        assert not re.search(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)',s),rel
        if p.suffix=='.md':
            for alt,target in re.findall(r'!\[([^\]]*)\]\(([^)]+)\)',s):
                assert alt.strip(),('missing image alt',rel,target)
            for target in re.findall(r'\]\(([^)]+)\)',s):
                if '://' in target or target.startswith('#') or target.startswith('mailto:'):continue
                target,_,fragment=target.partition('#')
                linked=p.parent/target
                assert linked.exists(),(rel,target)
                if re.fullmatch(r'L\d+',fragment):
                    assert 1<=int(fragment[1:])<=len(linked.read_text().splitlines()),(rel,target,fragment)
    print('Validated freeze, 450 independent qrels, graph ranges, budgets, publication links, image formats/alt text, file sizes and privacy patterns.')
if __name__=='__main__':main()
