"""Offline publication verification; stdlib only, no private cache or credentials."""
from collections import Counter
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
OUT = HERE / 'results'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
text_sha = lambda s: hashlib.sha256(s.encode()).hexdigest()
digest = lambda value: text_sha(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False))


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def main():
    state = read(OUT / 'execution.json')
    assert state['export_state'] == 'final' and state['synthetic'] is False
    assert state['status'] == 'complete_with_recorded_failures'
    statistics = module('summarize_execution')
    statistics.validate_ledger(state)
    constants = statistics.frozen_constants()
    queries = {q['id']: q for q in read(HERE / 'queries.json')}
    methods = ('routed_graphrag', 'bm25', 'ms_basic', 'hybrid')
    expected = {(q, m) for q in queries for m in methods}
    assert len(state['cells']) == 92
    assert {(c['question_id'], c['method']) for c in state['cells']} == expected
    assert Counter(c['status'] for c in state['cells']) == {'complete': 86, 'failed': 6}
    router = module('routing_rules')
    for q in queries.values():
        assert router.route(q['query']) == q['route']
    events = state['events']; assert len(events) == 193
    assert [e['sequence'] for e in events] == list(range(1, 194))
    assert max(Counter(e['key'] for e in events).values()) <= state['limits']['attempts_per_request']
    by_sequence = {e['sequence']: e for e in events}
    wires = {}
    for event in events:
        wire = read(OUT / f"wire/event-{event['sequence']:03d}.json")
        wires[event['sequence']] = wire
        assert wire['event'] == event
        body = wire['request']['body']
        assert wire['request']['service'] == event['service']
        encoded = json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        assert text_sha(encoded) == event['request_body_sha256']
        assert digest(wire['request']) == event['key'], 'Request cache key does not match service/body'
        envelope = wire['response_envelope']
        if envelope is not None:
            assert envelope.get('http_status') == event.get('http_status')
            for name in ('response_bytes', 'response_byte_limit'):
                if name in envelope:
                    assert envelope[name] == event.get(name)
            if envelope.get('http_status') == 200:
                assert event['status'] == 'validated'
                assert event.get('request_dispatched') is True or event.get('recovered_completed_reply') is True
                assert envelope['response_bytes'] <= envelope['response_byte_limit']
                assert envelope['response'].get('usage') == event.get('usage')
        if event.get('http_status') == 200:
            assert envelope is not None and 'response' in envelope
        assert event['input_tokens'] <= state['limits']['request_input' if event['service'] == 'generation' else 'embedding_item']
        if event['service'] == 'embedding' and envelope and 'response' in envelope:
            response = envelope['response']
            assert response['vectors_omitted'] is True
            assert response['dimensions'] == [3072] * response['vector_count']
            assert 'embedding' not in response and 'data' not in response
        if event['status'] == 'reviewed_non_dispatch':
            assert event['sequence'] == 1 and event['request_dispatched'] is False and envelope is None
    for record in state['cells']:
        cell = read(OUT / record['cell_file'])
        key = record['question_id'] + ':' + record['method']
        assert record['cell_file'] == f"cells/{record['question_id']}-{record['method']}.json"
        assert (cell['qid'], cell['method']) == (record['question_id'], record['method'])
        assert cell['status'] == record['status']
        assert text_sha(cell.get('answer') or '') == record['answer_sha256']
        if cell['method'] == 'routed_graphrag':
            assert cell['route'] == queries[cell['qid']]['route']['method']
        else:
            assert cell['route'] == cell['method']
        if cell['status'] == 'failed':
            assert not cell.get('answer')
        assert cell['generation_input_tokens'] <= state['limits']['cell_input']
        owned = [e for e in events if e['cell'] == key]
        generated = [e for e in owned if e['service'] == 'generation']
        assert cell['generation_input_tokens'] == record['generation_input_tokens_reserved'] == sum(e['input_tokens'] for e in generated)
        assert record['generation_reservations'] == len(generated)
        assert record['elapsed_seconds'] == cell['elapsed_seconds']
        assert record['known_provider_input_tokens'] == sum(e['usage']['prompt_tokens'] for e in generated if e.get('usage') is not None)
        assert record['known_provider_output_tokens'] == sum(e['usage']['completion_tokens'] for e in generated if e.get('usage') is not None)
        assert record['provider_usage_known_events'] == sum(e.get('usage') is not None for e in generated)
        assert record['provider_usage_unknown_possible_dispatch_events'] == sum(e.get('usage') is None and e.get('request_dispatched') is not False for e in generated)
        assert record['reviewed_non_dispatch_reservations'] == sum(e['status'] == 'reviewed_non_dispatch' for e in generated)
        assert len(cell['new_event_sequences']) == len(set(cell['new_event_sequences']))
        assert set(cell['new_event_sequences']) <= {e['sequence'] for e in owned}
        for event in owned:
            assert cell['requests'][event['key']] == {'stage': event['stage'], 'service': event['service']}
        logical_stages = Counter(r['stage'] for r in cell['requests'].values() if r['service'] == 'generation')
        assert all(n <= constants['STAGES'][cell['route']].get(stage, 0) for stage, n in logical_stages.items())
        assert cell['raw_sources_in_http200_contexts'] == record['raw_sources_in_http200_contexts']
        assert len({s['text_unit_id'] for s in cell['raw_sources_in_http200_contexts']}) == len(cell['raw_sources_in_http200_contexts'])
        actual = {e['sequence']: wires[e['sequence']]['request']['body'] for e in generated if e.get('http_status') == 200}
        for use in cell['uses']:
            origin = by_sequence[use['origin_event']]
            assert origin['key'] == use['key']
            assert origin['http_status'] == 200 and origin['status'] == 'validated'
            assert cell['requests'][use['key']] == {'stage': use['stage'], 'service': origin['service']}
            if use['cache']:
                if origin['service'] == 'generation':
                    actual[origin['sequence']] = wires[origin['sequence']]['request']['body']
            else:
                assert origin['cell'] == key
        assert record['cache_uses_without_new_physical_fee'] == sum(u['cache'] for u in cell['uses'])
        # Reconstruct exposure from actual HTTP200 request text, rather than
        # trusting exported source metadata or a rebuilt pack that copies it.
        exposures, sources, seen = [], [], set()
        for evidence in cell['evidence']:
            assert evidence['evidence_key'] == digest({k: v for k, v in evidence.items() if k not in {'evidence_key', 'read_occurrences'}})
            contexts = evidence['context'] if isinstance(evidence['context'], list) else [evidence['context']]
            for context in contexts:
                sequences = [seq for seq, body in actual.items() if context and any(context in message['content'][0]['text'] for message in body['input'])]
                exposures.append({'evidence_key': evidence['evidence_key'], 'context_sha256': text_sha(context),
                    'http200_generation_event_sequences': sequences,
                    'source_ids': [s['short_id'] for s in evidence.get('sources', [])] if sequences else []})
                if sequences:
                    for source in evidence.get('sources', []):
                        if source['text_unit_id'] not in seen:
                            sources.append(source); seen.add(source['text_unit_id'])
        assert cell['actual_context_exposure'] == exposures
        assert cell['raw_sources_in_http200_contexts'] == sources
    assert state['counts']['generation_reservations'] <= state['limits']['generation_reservations']
    assert state['counts']['generation_input_tokens'] <= state['limits']['generation_input_tokens']
    for name, result in [('aggregate_results', 'scores.json'), ('aggregate_evidence', 'evidence-scores.json'), ('summarize_execution', 'execution-statistics.json')]:
        assert module(name).calculate() == read(OUT / result), name
    mapping = read(OUT / 'grading-method-map.json')
    assert len(mapping) == 92 and len({m['anonymous_id'] for m in mapping}) == 92
    assert {(m['question_id'], m['method']) for m in mapping} == expected
    records = {(c['question_id'], c['method']): c for c in state['cells']}
    for item in mapping:
        assert item['cell_file'] == records[item['question_id'], item['method']]['cell_file']
    packed = []
    for batch in range(1, 8):
        packed.extend(read(OUT / f'grading-packs/blind-content-batch{batch}.json')['rows'])
    assert len(packed) == 92 and {r['anonymous_id'] for r in packed} == {m['anonymous_id'] for m in mapping}
    mapped = {m['anonymous_id']: m for m in mapping}
    for row in packed:
        identity = mapped[row['anonymous_id']]
        record = records[identity['question_id'], identity['method']]
        assert row['question_id'] == identity['question_id'] and row['query'] == queries[row['question_id']]['query']
        assert row['answer_sha256'] == record['answer_sha256'] == text_sha(row['answer'])
        assert row['status'] == ('completed' if record['status'] == 'complete' else 'failed')
    # Rebuild every actual-material review pack from public wires and cells.
    # The original packs stayed private during masking, but no private state is
    # needed to reconstruct them or verify every review's exact input hashes.
    builder = module('build_evidence_pack')
    with tempfile.TemporaryDirectory() as folder:
        builder.RUN = Path(folder)
        shutil.copyfile(OUT / 'grading-method-map.json', builder.RUN / 'blind-method-map.json')
        for batch in range(1, 8):
            shutil.copyfile(OUT / f'grading-packs/blind-content-batch{batch}.json', builder.RUN / f'blind-content-batch{batch}.json')
            with contextlib.redirect_stdout(io.StringIO()):
                builder.main(batch)
            generated = builder.RUN / f'blind-evidence-batch{batch}/manifest.json'
            published = OUT / f'evidence-manifests/batch{batch}.json'
            assert generated.read_bytes() == published.read_bytes(), batch
    manifest = read(OUT / 'export-manifest.json')
    required_files = {
        'execution.json', 'grading-method-map.json', 'scores.json',
        'evidence-scores.json', 'execution-statistics.json',
    }
    required_files.update(f'wire/event-{seq:03d}.json' for seq in by_sequence)
    required_files.update(c['cell_file'] for c in state['cells'])
    required_files.update(f'grading-packs/blind-content-batch{batch}.json' for batch in range(1, 8))
    required_files.update(f'evidence-manifests/batch{batch}.json' for batch in range(1, 8))
    files = {str(p.relative_to(OUT)): sha(p) for p in sorted(OUT.rglob('*.json')) if p.name != 'export-manifest.json'}
    assert set(files) == required_files, 'Missing or unexpected public data artifact'
    assert {str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file() and p.suffix != '.json'} <= {'README.md'}
    assert manifest['files'] == files
    assert manifest['script_sha256'] == sha(HERE / 'export_results.py')
    assert manifest['credential_reads'] == 0 and manifest['api_calls'] == 0
    print('Verified92cells/193events, frozen routes, budgets, request/answer hashes, all content/evidence scores, reconstructed7 review packs and publication manifest; API calls0.')


if __name__ == '__main__':
    main()
