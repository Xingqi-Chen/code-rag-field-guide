"""Verify pinned source bytes; never import or execute downloaded third-party code."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def safe_path(root, relative):
    parts = PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts or '\\' in relative:
        raise ValueError('Unsafe manifest path')
    candidate = root.joinpath(*parts.parts)
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError('Manifest path escapes source root')
    return candidate


def verify(data, record):
    assert hashlib.sha256(data).hexdigest() == record['sha256'], record['path']
    assert len(data) == record['byte_length'], record['path']
    lines = data.decode('utf-8').splitlines()
    assert len(lines) == record['line_count'], record['path']
    for span in record['line_ranges']:
        assert 1 <= span['start'] <= span['end'] <= len(lines), record['path']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true',
                        help='Fetch missing pinned raw files from official GitHub into ignored cache')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'research/microsoft-version.json').read_text())
    source = safe_path(ROOT, manifest['ignored_source_root'])
    prefix = f"https://raw.githubusercontent.com/microsoft/graphrag/{manifest['commit']}/"
    fetched = 0
    for record in manifest['source_files']:
        target = safe_path(source, record['path'])
        assert record['raw_url'] == prefix + record['path'], 'Unexpected source URL'
        if not target.exists() and args.fetch:
            with urlopen(record['raw_url'], timeout=45) as response:
                data = response.read(2_000_001)
            assert len(data) <= 2_000_000, 'Unexpectedly large source file'
            verify(data, record)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            fetched += 1
        if not target.is_file():
            raise SystemExit('Pinned cache incomplete; run python3 scripts/check_source.py --fetch')
        verify(target.read_bytes(), record)
    print(f"Verified {len(manifest['source_files'])} pinned source files (SHA-256, bytes, lines and citation ranges); fetched {fetched}.")
    print(f"Microsoft GraphRAG {manifest['tag']} / {manifest['commit']}")
    print('Static byte verification only; no third-party code executed, no model calls.')


if __name__ == '__main__':
    main()
