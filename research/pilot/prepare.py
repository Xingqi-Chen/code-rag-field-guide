"""Fetch a hash-pinned source snapshot; make shared inputs, never call a model."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / '.cache/pilot'
SPEC = json.loads((HERE / 'corpus.json').read_text())

def sha(data):
    return hashlib.sha256(data).hexdigest()

def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def source(fetch=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / 'requests.tar.gz'
    if not archive.exists():
        if not fetch:
            raise SystemExit('Missing archive; run with --fetch (public source download only).')
        with urllib.request.urlopen(SPEC['archive_url'], timeout=45) as response:
            data = response.read(20_000_001)
        assert len(data) <= 20_000_000, 'archive size limit'
        assert sha(data) == SPEC['archive_sha256'], 'archive SHA mismatch'
        archive.write_bytes(data)
    assert sha(archive.read_bytes()) == SPEC['archive_sha256'], 'archive SHA mismatch'
    target = CACHE / 'source'
    target.mkdir(exist_ok=True)
    # Do not import upstream setup.py or run any upstream installer.
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        assert sum(m.size for m in members) < 40_000_000
        for member in members:
            parts = PurePosixPath(member.name).parts
            assert parts and parts[0] == 'requests-' + SPEC['commit']
            assert '..' not in parts and not member.name.startswith('/')
            if member.isdir():
                continue
            if member.issym() and '/tests/certs/' in member.name:
                continue  # Public certificate-fixture links are outside this pilot.
            assert member.isfile(), 'links/devices are not accepted'
            dest = target.joinpath(*parts[1:])
            assert not dest.is_symlink()
            assert dest.resolve().is_relative_to(target.resolve()), 'path escapes snapshot'
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = tar.extractfile(member).read()
            if dest.exists():
                assert dest.read_bytes() == data, 'existing snapshot modified: ' + str(dest.relative_to(target))
            else:
                dest.write_bytes(data)
    assert sha((target / 'LICENSE').read_bytes()) == SPEC['license_sha256']
    return target

def build(snapshot):
    os.environ.setdefault('TIKTOKEN_CACHE_DIR', str(CACHE / 'tokenizer'))
    import tiktoken
    enc = tiktoken.get_encoding(SPEC['tokenizer'])
    count = lambda text: len(enc.encode(text, disallowed_special=()))
    files = sorted(set(p for pat in SPEC['include'] for p in snapshot.glob(pat)))
    records = []; manifest = []; seen = set(); empty = []
    for path in files:
        rel = path.relative_to(snapshot).as_posix()
        data = path.read_bytes(); text = data.decode('utf-8'); lines = text.splitlines(keepends=True)
        manifest.append(dict(path=rel, bytes=len(data), lines=len(lines), tokens=count(text), sha256=sha(data)))
        if not text.strip():
            empty.append(rel); continue
        start = 0
        while start < len(lines):
            end = start
            while end < len(lines) and count(''.join(lines[start:end + 1])) <= SPEC['chunk_tokens']:
                end += 1
            assert end > start, 'single line exceeds token budget: ' + rel
            chunk = ''.join(lines[start:end]); chunk_hash = sha(chunk.encode())
            assert chunk_hash not in seen, 'duplicate body requires explicit multi-source policy'
            seen.add(chunk_hash)
            doc_id = sha((SPEC['commit'] + ':' + rel + ':' + str(start + 1) + ':' + str(end)).encode())
            records.append(dict(id=doc_id, title=f'{rel}:L{start+1}-L{end}', text=chunk,
                                path=rel, start_line=start+1, end_line=end, tokens=count(chunk),
                                text_sha256=chunk_hash, ms_text_unit_id=hashlib.sha512(chunk.encode()).hexdigest()))
            if end == len(lines):
                break
            next_start = end
            while next_start > start + 1 and count(''.join(lines[next_start-1:end])) <= SPEC['overlap_tokens_max']:
                next_start -= 1
            start = next_start
    inputs = CACHE / 'input'; inputs.mkdir(exist_ok=True)
    (inputs / 'documents.jsonl').write_text(''.join(json.dumps({k:r[k] for k in ('id','title','text')}, ensure_ascii=False)+'\n' for r in records))
    dump(CACHE / 'provenance.json', [{k:v for k,v in r.items() if k != 'text'} for r in records])
    dump(CACHE / 'files.json', manifest)
    summary = dict(commit=SPEC['commit'], files=len(files), bytes=sum(f['bytes'] for f in manifest),
                   lines=sum(f['lines'] for f in manifest), tokens=sum(f['tokens'] for f in manifest),
                   chunks=len(records), chunk_tokens_with_overlap=sum(r['tokens'] for r in records),
                   max_chunk_tokens=max(r['tokens'] for r in records), empty_files_not_indexed=empty,
                   source_files=sum(f['path'].startswith('src/') for f in manifest),
                   test_files=sum(f['path'].startswith('tests/') for f in manifest),
                   input_sha256=sha((inputs / 'documents.jsonl').read_bytes()),
                   file_manifest_sha256=sha((CACHE / 'files.json').read_bytes()),
                   provenance_sha256=sha((CACHE / 'provenance.json').read_bytes()),
                   inference_requests=0)
    dump(CACHE / 'size.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    args=parser.parse_args()
    build(source(args.fetch))

if __name__=='__main__':
    main()
