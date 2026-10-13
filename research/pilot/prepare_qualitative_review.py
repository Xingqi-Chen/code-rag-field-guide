"""Prepare the four predeclared cases without method labels, offline.

Reviewers are AI agents, not human annotators. Context layout can reveal a
method, so this is label masking, not a claim of a fully blinded experiment.
Do not change the frozen gold or quantitative scores after these reviews.
"""
import json
from pathlib import Path
import random

from result_paths import OUT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ['Q01', 'Q07', 'Q13', 'Q20']
METHODS = ['bm25', 'hybrid', 'ms_basic', 'ms_local']


def main():
    destination = ROOT / '.cache/pilot/qualitative-review'
    destination.mkdir(exist_ok=False)
    questions = {q['id']: q for q in json.loads((HERE/'questions.json').read_text())}
    gold = {q['id']: q for q in json.loads((HERE/'gold.json').read_text())}
    rng = random.Random(20261012)
    mapping = []
    for qid in CASES:
        methods = METHODS.copy()
        rng.shuffle(methods)
        case = {'question_id': qid, 'query': questions[qid]['query'],
                'frozen_gold': gold[qid], 'contexts': []}
        for label, method in zip('ABCD', methods, strict=True):
            name = f'{qid}-{method}-4000.json'
            context = json.loads((OUT/'contexts'/name).read_text())
            case['contexts'].append({'label': label, 'text': context['final_context']})
            mapping.append({'question_id': qid, 'label': label, 'method': method,
                            'context_file': 'contexts/'+name})
        (destination/f'{qid}.json').write_text(json.dumps(case, ensure_ascii=False, indent=2)+'\n')
    # Keep the key outside the reviewers' packet directory until reviews end.
    (ROOT/'.cache/pilot/qualitative-key.json').write_text(json.dumps(mapping, indent=2)+'\n')
    print('Prepared four label-masked 4000-token case packets; no provider calls.')


if __name__ == '__main__':
    main()
