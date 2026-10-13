"""Inspect existing replies with the pinned official parser; no provider calls."""
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
import re

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'

from result_paths import OUT

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT/'.cache/pilot/full-20261012'


def main():
    from graphrag.index.operations.extract_graph.graph_extractor import (
        GraphExtractor, TUPLE_DELIMITER, RECORD_DELIMITER)
    diagnostics = json.loads((OUT/'extraction-format-diagnostics.json').read_text())
    groups = defaultdict(dict)
    wrong = []
    for item in diagnostics:
        seq = item['sequence']
        request = json.loads((RUN/f'request-{seq:02}.json').read_text())
        reply = json.loads((RUN/f'response-{seq:02}.json').read_text())['response']
        choice = reply['choices'][0]
        text = choice['message']['content']
        key = request['body']['input'][0]['content'][0]['text']
        groups[key][item['operation']] = (seq, text)
        if not item['ends_with_expected_complete_marker']:
            suffix = re.search(r'(<\|>COMPLETE(?:<\|>|\|>))\s*$', text)
            wrong.append({'sequence': seq,
                'normalized_finish_reason': choice.get('finish_reason'),
                'wrong_terminal_marker': suffix.group(1) if suffix else None,
                'completion_tokens': reply['usage']['completion_tokens']})
    parser = GraphExtractor(model=None, prompt='', max_gleanings=0)
    rows = []
    for group in groups.values():
        initial_seq, first = group['extraction_initial']
        glean_seq, last = group['extraction_glean']
        combined = first + last  # Exact upstream concatenation, no repair.
        entities, relations = parser._process_result(
            combined, 'offline-diagnostic', TUPLE_DELIMITER, RECORD_DELIMITER)
        fallback = 0
        for raw in combined.split(RECORD_DELIMITER):
            fields = re.sub(r'^\(|\)$', '', raw.strip()).split(TUPLE_DELIMITER)
            if fields[0] == '"relationship"' and len(fields) >= 5:
                try:
                    float(fields[-1])
                except ValueError:
                    fallback += 1
        rows.append({'initial_sequence': initial_seq, 'glean_sequence': glean_seq,
            'parsed_entity_records': len(entities), 'parsed_relation_records': len(relations),
            'relations_with_weight_fallback': fallback})
    affected = [r for r in rows if any(w['sequence'] in
        (r['initial_sequence'], r['glean_sequence']) for w in wrong)]
    result = {'scope': 'Offline parse of existing initial+glean replies, before graph merge; no output repair or inference calls.',
        'wrong_marker_variants': dict(Counter(w['wrong_terminal_marker'] for w in wrong)),
        'all_wrong_marker_replies_have_normalized_stop': all(w['normalized_finish_reason']=='stop' for w in wrong),
        'wrong_marker_replies': wrong, 'parsed_chunks': rows,
        'totals_before_merge': {k: sum(r[k] for r in rows) for k in
            ['parsed_entity_records','parsed_relation_records','relations_with_weight_fallback']},
        'chunks_with_wrong_marker': affected,
        'interpretation': 'Wrong terminal spellings are not proof of transport truncation. The official parser tolerates malformed fields and uses weight 1.0 when float parsing fails. Neither successful indexing nor these counts establish extraction completeness or code-semantic correctness.'}
    (OUT/'extraction-parser-diagnostics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'chunks': len(rows), 'affected_chunks': len(affected), **result['totals_before_merge']}))


if __name__ == '__main__':
    main()
