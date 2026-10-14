"""Recompute non-overlapping execution costs from the published final ledger."""
import argparse
import ast
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'results'
read = lambda p: json.loads(p.read_text())


def frozen_constants():
    """Read literal, hash-reviewed runtime configuration without importing it."""
    tree = ast.parse((HERE / 'runtime/bounded.py').read_text())
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {'CARRY', 'LIMITS', 'STAGES'}:
                    values[target.id] = ast.literal_eval(node.value)
    assert set(values) == {'CARRY', 'LIMITS', 'STAGES'}
    return values


def validate_ledger(state):
    constants = frozen_constants()
    assert state['carry'] == constants['CARRY'], 'Frozen carry changed'
    assert state['limits'] == constants['LIMITS'], 'Frozen limits changed'
    limits = constants['LIMITS']
    cells = {c['question_id'] + ':' + c['method']: c for c in state['cells']}
    assert len(cells) == len(state['cells'])
    for c in cells.values():
        assert c['method'] in {'routed_graphrag', 'bm25', 'ms_basic', 'hybrid'}
        assert isinstance(c['elapsed_seconds'], (int, float)) and math.isfinite(c['elapsed_seconds']) and c['elapsed_seconds'] >= 0
    for e in state['events']:
        assert e['cell'] in cells, 'Unknown event owner'
        assert e['service'] in {'generation', 'embedding'}
        assert e['synthetic'] is False
        assert type(e['input_tokens']) is int and e['input_tokens'] > 0
        assert e['input_tokens'] <= limits['request_input' if e['service'] == 'generation' else 'embedding_item']
        assert e.get('request_dispatched') is None or type(e['request_dispatched']) is bool
        assert isinstance(e.get('elapsed_seconds', 0), (int, float)) and math.isfinite(e.get('elapsed_seconds', 0)) and e.get('elapsed_seconds', 0) >= 0
        usage = e.get('usage')
        if usage is not None:
            required = {'prompt_tokens', 'total_tokens'} | ({'completion_tokens'} if e['service'] == 'generation' else set())
            assert isinstance(usage, dict) and required <= usage.keys(), 'Incomplete usage must not become zero'
            assert all(type(usage[k]) is int and usage[k] >= 0 for k in required)
            if e['service'] == 'generation':
                assert usage['total_tokens'] == usage['prompt_tokens'] + usage['completion_tokens']
    assert set(state['counts']) == set(constants['CARRY'])
    assert all(type(n) is int and n >= 0 for n in state['counts'].values())
    generation = [e for e in state['events'] if e['service'] == 'generation']
    embedding = [e for e in state['events'] if e['service'] == 'embedding']
    delta = {k: state['counts'][k] - v for k, v in state['carry'].items()}
    assert delta == {
        'generation_reservations': len(generation),
        'generation_input_tokens': sum(e['input_tokens'] for e in generation),
        'embedding_tokens': sum(e['input_tokens'] for e in embedding),
        'embedding_attempts': len(embedding),
    }
    for name in ('generation_reservations', 'generation_input_tokens', 'embedding_attempts'):
        assert state['counts'][name] <= limits[name], name
    assert Decimal(state['counts']['embedding_tokens']) * Decimal('0.13') / 1000000 <= Decimal(limits['embedding_usd'])
    for key, c in cells.items():
        tokens = sum(e['input_tokens'] for e in generation if e['cell'] == key)
        assert c['generation_input_tokens_reserved'] == tokens <= limits['cell_input']
    return delta


def calculate():
    state = read(OUT / 'execution.json')
    events = state['events']
    generation = [e for e in events if e['service'] == 'generation']
    embedding = [e for e in events if e['service'] == 'embedding']
    delta = validate_ledger(state)
    methods = []
    for method in ('routed_graphrag', 'bm25', 'ms_basic', 'hybrid'):
        rows = [c for c in state['cells'] if c['method'] == method]
        selected = [e for e in events if e['cell'].endswith(':' + method)]
        gen = [e for e in selected if e['service'] == 'generation']
        methods.append({
            'method': method, 'unique_questions': len(rows),
            'final_answers': sum(c['status'] == 'complete' for c in rows),
            'generation_reservations': len(gen),
            'physical_generation_attempts': sum(e.get('request_dispatched') is True for e in gen),
            'common_input_tokens_reserved': sum(e['input_tokens'] for e in gen),
            'provider_known_input_tokens': sum((e.get('usage') or {}).get('prompt_tokens', 0) for e in gen),
            'provider_known_output_tokens': sum((e.get('usage') or {}).get('completion_tokens', 0) for e in gen),
            'provider_usage_unknown_events': [e['sequence'] for e in gen if e.get('usage') is None and e.get('request_dispatched') is not False],
            'new_embedding_attempts': sum(e['service'] == 'embedding' for e in selected),
            'new_embedding_tokens': sum(e['input_tokens'] for e in selected if e['service'] == 'embedding'),
            'cell_execution_seconds': sum(c['elapsed_seconds'] for c in rows),
        })
    return {
        'execution_sha256': hashlib.sha256((OUT / 'execution.json').read_bytes()).hexdigest(),
        'completion_counts': dict(Counter(c['status'] for c in state['cells'])),
        'failed_questions': [c['question_id'] for c in state['cells'] if c['status'] == 'failed'],
        'carry': state['carry'], 'delta': delta, 'cumulative': state['counts'],
        'physical_generation_attempts': sum(e.get('request_dispatched') is True for e in generation),
        'http200_generation_attempts': sum(e.get('http_status') == 200 for e in generation),
        'reviewed_non_dispatch_events': [e['sequence'] for e in generation if e['status'] == 'reviewed_non_dispatch'],
        'requested_output_limit_exceeded_events': [e['sequence'] for e in generation if e.get('requested_output_limit_exceeded')],
        'provider_known_input_tokens': sum(e['usage']['prompt_tokens'] for e in generation if e.get('usage') is not None),
        'provider_known_output_tokens': sum(e['usage']['completion_tokens'] for e in generation if e.get('usage') is not None),
        'provider_usage_unknown_events': [e['sequence'] for e in generation if e.get('usage') is None and e.get('request_dispatched') is not False],
        'recorded_request_seconds': sum(e.get('elapsed_seconds', 0) for e in events),
        'cell_execution_seconds': sum(c['elapsed_seconds'] for c in state['cells']),
        'embedding_price_usd_per_million_frozen': '0.13',
        'embedding_cumulative_estimate_usd': str(Decimal(state['counts']['embedding_tokens']) * Decimal('0.13') / 1000000),
        'embedding_new_estimate_usd': str(Decimal(delta['embedding_tokens']) * Decimal('0.13') / 1000000),
        'methods_unique23': methods,
        'limitations': [
            'No quality score is averaged over all23; main16/dev4 and supplemental6 remain separate.',
            'Cumulative counters continue the authorized code-prompt/routing ledger; they are not all historical project spending.',
            'Common-token reservations and provider-reported usage use different counting conventions.',
            f"{sum(e.get('usage') is None and e.get('request_dispatched') is not False for e in generation)} possibly dispatched generation attempts have unknown provider usage; known totals are incomplete.",
            'Physical attempts count local dispatch-start markers, not proof of remote receipt or billing.',
            'Elapsed time is incremental execution, with cached one-shot contexts but dynamic DRIFT contexts.',
            'Graph construction is a previous phase; it is not charged again in these incremental costs.',
            'Generation currency cost and peak memory were not measured.',
        ],
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--check', action='store_true')
    args = p.parse_args(); result = calculate(); path = OUT / 'execution-statistics.json'
    if args.check:
        assert read(path) == result
    else:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'methods_unique23'}, ensure_ascii=False))
