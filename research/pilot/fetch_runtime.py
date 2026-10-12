"""Download/extract hash-pinned official GraphRAG source and token vocabularies.

Does not install packages, import upstream code, load credentials or call a model.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[2]


def main():
    manifest=json.loads((ROOT/'research/microsoft-version.json').read_text())
    archive=ROOT/manifest['ignored_archive_path']
    archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        with urllib.request.urlopen(manifest['download_url'],timeout=60) as response:
            data=response.read(20_000_001)
        assert len(data)<=20_000_000
        assert hashlib.sha256(data).hexdigest()==manifest['archive_sha256']
        archive.write_bytes(data)
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['archive_sha256']
    target=ROOT/manifest['ignored_source_root']
    target.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers()
        assert sum(m.size for m in members)<100_000_000
        written=0
        for member in members:
            parts=PurePosixPath(member.name).parts
            assert parts[0]=='graphrag-'+manifest['commit'] and '..' not in parts
            relative=parts[1:]
            if not relative or (relative[0]!='packages' and relative!=('LICENSE',)):continue
            if member.isdir():continue
            assert member.isfile(), 'non-regular runtime archive member'
            path=target.joinpath(*relative)
            assert not path.is_symlink() and path.resolve().is_relative_to(target.resolve())
            data=tar.extractfile(member).read()
            if path.exists():assert path.read_bytes()==data, 'existing runtime source changed'
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data);written+=1
    print(f'Pinned official archive verified; runtime files added: {written}. No code executed.')
    cache=ROOT/'.cache/pilot/tokenizer'
    cache.mkdir(parents=True,exist_ok=True)
    for name,sha in [('cl100k_base','223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7'),
                     ('o200k_base','446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d')]:
        url=f'https://openaipublic.blob.core.windows.net/encodings/{name}.tiktoken'
        path=cache/hashlib.sha1(url.encode()).hexdigest()
        if not path.exists():
            with urllib.request.urlopen(url,timeout=45) as response:data=response.read(5_000_001)
            assert len(data)<=5_000_000 and hashlib.sha256(data).hexdigest()==sha
            path.write_bytes(data)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    print('Both small public token vocabularies verified. No model or credential access.')


if __name__=='__main__':main()
