"""Offline, standard-library checks for the Microsoft GraphRAG literature guide."""
import json
from pathlib import Path
import re
import subprocess
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

def prose_only(text):
    """Remove fenced/inline code before treating text as Markdown links/headings."""
    lines=[]; fence=None
    for line in text.splitlines():
        marker=re.match(r'^ {0,3}(`{3,}|~{3,})',line)
        if marker:
            token=marker[1]
            if fence is None:fence=token
            elif token[0]==fence[0] and len(token)>=len(fence):fence=None
            continue
        if fence is None:lines.append(line)
    return re.sub(r'(`+).*?\1','', '\n'.join(lines))

def anchors(text):
    result=set(); counts={}
    for line in prose_only(text).splitlines():
        if not re.match(r'^#{1,6} ',line):continue
        heading=re.sub(r'^#{1,6} +','',line).strip().lower()
        heading=re.sub(r'[^\w\- ]','',heading).replace(' ','-')
        count=counts.get(heading,0);counts[heading]=count+1
        result.add(heading+(f'-{count}' if count else ''))
    return result

def main():
    files=subprocess.check_output(['git','-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
    files=sorted(set(filter(None,files))); links=0; pngs=0
    for rel in files:
        p=ROOT/rel
        assert not rel.startswith(('.cache/','.venv/')),rel
        assert p.is_file() and not p.is_symlink(),rel
        assert p.stat().st_size<2_000_000,rel
        if p.suffix=='.png':
            width,height=check_png(p.read_bytes());pngs+=1
            sw,sh=check_svg(p.with_suffix('.svg').read_text())
            assert (width,height)==(sw*2,sh*2),rel
            continue
        s=p.read_text()
        assert not re.search(r'/(?:Users|home)/[A-Za-z0-9_-]+/',s),rel
        assert not re.search(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)',s),rel
        if p.suffix=='.svg':
            check_svg(s);assert p.with_suffix('.png').exists(),rel
        if p.suffix=='.md':
            s=prose_only(s)
            for alt,target in re.findall(r'!\[([^\]]*)\]\(([^)]+)\)',s):
                assert alt.strip(),('missing image alt',rel,target)
            for target in re.findall(r'\]\(([^)]+)\)',s):
                if '://' in target or target.startswith('mailto:'):continue
                target,_,fragment=target.partition('#');linked=p.parent/target if target else p
                assert linked.is_file(),(rel,target)
                if re.fullmatch(r'L\d+',fragment):
                    assert 1<=int(fragment[1:])<=len(linked.read_text().splitlines()),(rel,target,fragment)
                elif fragment and linked.suffix=='.md':
                    assert fragment in anchors(linked.read_text()),(rel,target,fragment)
                links+=1
    assert pngs==4,('expected four published diagrams',pngs)
    version=json.loads((ROOT/'research/microsoft-version.json').read_text())
    assert '5faaaf4f5685fa2056fa8c3bf9342cb089f2942f' in json.dumps(version),'fixed Microsoft source revision'
    assert not (ROOT/'results').exists() and not (ROOT/'benchmark').exists(),'old experiment belongs in Git history'
    print(f'Validated {len(files)} public files, {links} local links/anchors, 4 PNG/SVG pairs, source pin and privacy patterns.')
if __name__=='__main__':main()
