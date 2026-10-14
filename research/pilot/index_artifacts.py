"""Lossless, hash-checked JSON pages for large public graph tables."""
import hashlib
import json
from pathlib import Path


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()


def rows_sha(rows):
    data=json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def write_table(path,rows,*,split_if_bytes=1900000,page_bytes=1500000):
    path=Path(path);assert isinstance(rows,list)
    raw=encoded(rows);path.parent.mkdir(parents=True,exist_ok=True)
    if len(raw)<=split_if_bytes:
        path.write_bytes(raw)
        return {'format':'json-array','rows':len(rows),'logical_rows_sha256':rows_sha(rows)}
    directory=path.with_suffix('');directory.mkdir(exist_ok=False)
    groups=[];current=[]
    for row in rows:
        assert len(encoded([row]))<=page_bytes,'Single public record exceeds the page budget'
        if current and len(encoded(current+[row]))>page_bytes:
            groups.append(current);current=[]
        current.append(row)
    if current:groups.append(current)
    parts=[]
    for i,group in enumerate(groups,1):
        part=directory/f'part-{i:03}.json';data=encoded(group);part.write_bytes(data)
        parts.append({'file':str(part.relative_to(path.parent)),'rows':len(group),
            'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    manifest={'format':'paged-json-table-v1','rows':len(rows),'logical_rows_sha256':rows_sha(rows),
        'note':'Concatenate the arrays in parts order. No graph record or field is omitted; original row order is preserved.',
        'parts':parts}
    path.write_bytes(encoded(manifest))
    return manifest


def read_table(path):
    path=Path(path);value=json.loads(path.read_bytes())
    if isinstance(value,list):return value
    assert value['format']=='paged-json-table-v1'
    rows=[];seen=set()
    for part in value['parts']:
        relative=Path(part['file'])
        assert not relative.is_absolute() and '..' not in relative.parts
        assert relative.parts[0]==path.stem and relative.as_posix() not in seen
        seen.add(relative.as_posix());data=(path.parent/relative).read_bytes()
        assert len(data)==part['bytes'] and hashlib.sha256(data).hexdigest()==part['sha256']
        page=json.loads(data);assert isinstance(page,list) and len(page)==part['rows']
        rows.extend(page)
    assert len(rows)==value['rows'] and rows_sha(rows)==value['logical_rows_sha256']
    return rows
