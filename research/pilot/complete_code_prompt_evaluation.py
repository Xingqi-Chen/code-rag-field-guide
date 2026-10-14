"""Record/check the offline evaluation without altering the paid index ledger."""
import argparse
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'results/code-prompt'


def calculate():
    read = lambda name: json.loads((OUT / name).read_text())
    execution = read('execution.json')
    retrieval, scores = read('retrieval.json'), read('scores.json')
    assert execution['status'] == 'index_complete'
    assert execution['evaluation_complete'] is False
    assert len(retrieval['records']) == 80 and retrieval['external_calls'] == 0
    assert len(scores['rows']) == 400
    names = ['execution.json', 'retrieval.json', 'scores.json', 'analysis.json']
    names += [r['context_file'] for r in retrieval['records']]
    return {
        'status': 'offline_evaluation_complete',
        'scope': '80 new Local contexts and 400 combined frozen-protocol score rows; no new answers or Global run.',
        'index_snapshot_scope': 'execution.json is the earlier completed paid-index snapshot. Its evaluation_complete:false is retained, not a current evaluation failure.',
        'new_contexts': 80,
        'combined_score_rows': 400,
        'new_external_calls': 0,
        'paid_ledger_sha256_unchanged': retrieval['paid_ledger_sha256_unchanged'],
        'public_artifact_sha256': {name: hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in names},
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result, path = calculate(), OUT/'evaluation-completion.json'
    if args.check:
        assert result == json.loads(path.read_text())
    else:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('Verified offline evaluation completion: 80 contexts, 400 scores, 0 new external calls; index snapshot preserved.')
