"""Verify published one-shot feature evidence offline, without executing patches."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

from full_features import PROMPT, extract_diff
from result_paths import OUT

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    features = {f['id']: f for f in json.loads((HERE/'features.json').read_text())}
    manifest = json.loads((OUT/'feature-generations.json').read_text())
    expected = {(f, m) for f in features for m in ['bm25', 'hybrid', 'ms_basic', 'ms_local']}
    seen, counts = set(), Counter()
    for row in manifest['results']:
        pair = row['feature_id'], row['method']
        assert pair in expected and pair not in seen, 'duplicate or unknown feature result'
        seen.add(pair)
        label = '-'.join(pair)
        response = (OUT/'features'/f'{label}.response.txt').read_bytes()
        assert digest(response) == row['response_sha256'], 'original response changed'
        patch, issue = extract_diff(response.decode())
        assert issue == row['patch_format_issue']
        context = json.loads((OUT/row['context_file']).read_text())
        assert context['question_id'] == pair[0] and context['method'] == pair[1]
        assert context['budget'] == 4000 and context['final_context_tokens'] == row['context_tokens'] <= 4000
        prompt = PROMPT.format(task=features[pair[0]]['query'], context=context['final_context'])
        assert digest(prompt.encode()) == row['prompt_sha256'], 'prompt changed'
        evaluation = json.loads((OUT/'features'/f'{label}-evaluation.json').read_text())
        assert evaluation['generation'] == row
        assert (evaluation['feature_id'], evaluation['method']) == pair
        if patch is None:
            assert row['patch_sha256'] is None and evaluation['status'] == 'invalid_format'
            assert evaluation['suites'] == []
        else:
            data = (OUT/'features'/f'{label}.patch').read_bytes()
            assert data == patch.encode() and digest(data) == row['patch_sha256']
            review = json.loads((OUT/'features'/f'{label}-review.json').read_text())
            assert review == evaluation['manual_review']
            assert review['approved_for_isolated_tests'] is True
            assert review['response_sha256'] == row['response_sha256']
            assert review['patch_sha256'] == row['patch_sha256']
            if evaluation['status'] == 'patch_did_not_apply':
                assert evaluation['patch_check_exit_code'] != 0 and evaluation['suites'] == []
                # Parse only: no source checkout or patch execution is required.
                if 'corrupt patch' in evaluation['patch_check_diagnostic']:
                    parsed = subprocess.run(['git', 'apply', '--numstat'], input=data, capture_output=True)
                    assert parsed.returncode != 0 and b'corrupt patch' in parsed.stderr
            else:
                assert evaluation['status'] == 'tested' and evaluation['patch_check_exit_code'] == 0
                assert {s['suite'] for s in evaluation['suites']} == {pair[0], 'regression'}
        usage = row['usage']
        assert usage['prompt_tokens'] + usage['completion_tokens'] == usage['total_tokens']
        counts[evaluation['status']] += 1
    assert seen == expected, 'incomplete feature grid'
    execution = json.loads((OUT/'execution.json').read_text())
    assert sum(r['physical_generation_attempts'] for r in manifest['results']) == execution['feature_generation_attempts']
    print(json.dumps({'verified_feature_attempts': len(seen), 'statuses': dict(counts),
                      'executed_candidate_code': False}))


if __name__ == '__main__':
    main()
