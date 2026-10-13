"""Tiny offline probe of pinned upstream delta/concatenation functions.

Run with the existing GraphRAG 3.3.0 environment. This does not run an index,
generate embeddings, or measure realistic update latency. All tables are memory-only.
"""
import asyncio
import hashlib
import inspect
import json
from pathlib import Path
import sys


def no_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'http.client.connect'}:
        raise RuntimeError('Network is forbidden')


sys.addaudithook(no_network)


async def main():
    import pandas as pd
    from graphrag.index.update import incremental_index as upstream
    root = Path(__file__).resolve().parents[2]
    pinned = root / '.cache/ms-graphrag/graphrag-5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/index/update/incremental_index.py'
    actual = Path(inspect.getfile(upstream))
    assert actual.read_bytes() == pinned.read_bytes(), 'Not the pinned implementation'

    class Tables:
        def __init__(self, frame=None):
            self.frame = frame

        async def read_dataframe(self, name):
            assert name == 'documents'
            return self.frame.copy(deep=True)

        async def write_dataframe(self, name, frame):
            assert name == 'documents'
            self.frame = frame.copy(deep=True)

    old = pd.DataFrame([
        {'id': 'old-a', 'human_readable_id': 0, 'title': 'a.py', 'text': 'def send(): return 1'},
        {'id': 'old-b', 'human_readable_id': 1, 'title': 'b.py', 'text': 'def helper(): return 2'}])
    edited = old.copy(deep=True)
    edited.loc[0, ['id', 'text']] = ['new-a', 'def send(): return helper()']
    new_row = {'id': 'new-c', 'human_readable_id': 0, 'title': 'c.py', 'text': 'def added(): return 3'}
    renamed = old.copy(deep=True)
    renamed.loc[1, ['id', 'title']] = ['renamed-b', 'c.py']
    inputs = {'same_title_body_edit': edited, 'new_title': pd.concat([old, pd.DataFrame([new_row])]),
              'delete_b': old.iloc[:1].copy(), 'rename_b_to_c': renamed}
    results = []
    for name, current in inputs.items():
        delta = await upstream.get_delta_docs(current, Tables(old))
        # This tests concat separately even when the loader would stop on no new rows.
        merged = await upstream.concat_dataframes('documents', Tables(old), Tables(delta.new_inputs), Tables())
        results.append({'case': name, 'input': current.to_dict('records'),
            'new_titles': delta.new_inputs['title'].tolist(), 'deleted_titles': delta.deleted_inputs['title'].tolist(),
            'merged_by_concat': merged.to_dict('records'), 'default_loader_would_stop': len(delta.new_inputs) == 0})
    assert results[0]['new_titles'] == []
    assert results[0]['merged_by_concat'][0]['text'] == old.iloc[0]['text']
    assert results[2]['deleted_titles'] == ['b.py'] and len(results[2]['merged_by_concat']) == 2
    assert [x['title'] for x in results[3]['merged_by_concat']] == ['a.py', 'b.py', 'c.py']
    record = {'scope': 'Actual pinned upstream functions with synthetic in-memory tables; no full pipeline, model, embedding, vector store, or performance experiment.',
        'microsoft_commit': '5faaaf4f5685fa2056fa8c3bf9342cb089f2942f',
        'upstream_file_sha256': hashlib.sha256(actual.read_bytes()).hexdigest(),
        'upstream_file': 'packages/graphrag/graphrag/index/update/incremental_index.py',
        'cases': results, 'new_external_calls': 0}
    target = root / 'research/pilot/results/failure-analysis/update-semantics.json'
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print('Verified four synthetic update cases with actual pinned functions; zero external calls.')


if __name__ == '__main__':
    asyncio.run(main())
