"""Offline freeze checks. --source additionally verifies the ignored snapshot."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name):return json.loads((HERE/name).read_text())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',action='store_true')
    args=parser.parse_args()
    freeze=read('freeze.json')
    for rel,expected in freeze['sha256'].items():
        path=HERE/rel
        assert path.resolve().is_relative_to(HERE) and not path.is_symlink()
        assert digest(path)==expected, 'freeze mismatch: '+rel
    questions=read('questions.json');features=read('features.json')
    gold=read('gold.json')+read('feature-gold.json')
    assert len(questions)==20 and len(features)==2
    assert {q['id'] for q in questions if q['split']=='dev'}=={'Q03','Q04','Q06','Q11'}
    assert len({q['id'] for q in questions+features})==22
    assert {g['id'] for g in gold}=={q['id'] for q in questions+features}
    spec=read('corpus.json');files=read('files.json');allowed={f['path'] for f in files}
    spans=[e for g in gold for e in g['evidence']]
    for e in spans:
        assert e['path'] in allowed and 1<=e['start_line']<=e['end_line']
    assert len(allowed)==41
    # A query ranking cannot be an answer patch or a model result in this release.
    assert freeze['model_execution_started'] is False
    if args.source:
        source=ROOT/'.cache/pilot/source'
        for f in files:
            assert digest(source/f['path'])==f['sha256'],f['path']
        assert digest(source/'LICENSE')==spec['license_sha256']
        for e in spans:
            lines=(source/e['path']).read_text().splitlines()
            data=('\n'.join(lines[e['start_line']-1:e['end_line']])+'\n').encode()
            assert hashlib.sha256(data).hexdigest()==e['span_sha256'],e['id']
        for f in files:
            if f['path'].endswith('.py'):
                tree=ast.parse((source/f['path']).read_text())
                assert not any(isinstance(n,ast.ClassDef) and n.name=='AsyncSession' for n in ast.walk(tree))
        size=read('size.json')
        assert digest(ROOT/'.cache/pilot/input/documents.jsonl')==size['input_sha256']
        assert digest(ROOT/'.cache/pilot/provenance.json')==size['provenance_sha256']
        assert digest(ROOT/'.cache/pilot/files.json')==size['file_manifest_sha256']
    print(f'Freeze verified: 20 retrieval + 2 feature tasks; {len(spans)} source spans; 41 input files; source_check={args.source}; no inference.')

if __name__=='__main__':main()
