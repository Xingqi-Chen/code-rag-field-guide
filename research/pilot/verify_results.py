"""Validate actual public contexts and reconstruct scored provenance, offline."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from full_retrieve import render, adapt, budget_tables

HERE=Path(__file__).resolve().parent
from result_paths import OUT


def validate(tokens=False):
    questions=json.loads((HERE/'questions.json').read_text())
    features=json.loads((HERE/'features.json').read_text())
    methods=['bm25','hybrid','ms_basic','ms_local']
    expected={(q['id'],m,b) for q in questions+features for m in methods
              for b in ([4000,12000] if q['id'].startswith('Q') else [4000])}
    data=json.loads((OUT/'retrieval.json').read_text())
    actual=[(r['question_id'],r['method'],r['budget']) for r in data['records']]
    assert len(actual)==len(set(actual)) and set(actual)==expected, 'incomplete/duplicate evaluation grid'
    sidecar=OUT/'provenance.json'
    assert hashlib.sha256(sidecar.read_bytes()).hexdigest()==json.loads((HERE/'size.json').read_text())['provenance_sha256']
    provenance={p['id']:p for p in json.loads(sidecar.read_text())}
    short_map=json.loads((OUT/'short-id-map.json').read_text())
    assert len(short_map)==114 and len({s['text_unit_id'] for s in short_map})==114
    assert {s['input_id'] for s in short_map}==set(provenance)
    by_short={s['short_id']:s for s in short_map}
    assert len(by_short)==114
    for s in short_map:
        assert s['text_unit_id']==provenance[s['input_id']]['ms_text_unit_id']
    count=None
    if tokens:
        import probe_runtime
        enc,_=probe_runtime.tokenizers()
        count=lambda text:len(enc.encode(text,disallowed_special=()))
    rebuilt=[]
    files=set()
    for result in data['records']:
        name=f'{result["question_id"]}-{result["method"]}-{result["budget"]}.json'
        assert result['context_file']=='contexts/'+name
        files.add(name)
        context=json.loads((OUT/'contexts'/name).read_text())
        for k in ('question_id','method','budget'):assert context[k]==result[k]
        assert context['query']==next(q['query'] for q in questions+features if q['id']==context['question_id'])
        assert render(context['final_tables'])==context['final_context'], 'context differs from its scored tables'
        assert context['final_context_tokens']<=context['budget']
        assert context['retrieval_compute_seconds']>=0 and context['adaptation_seconds']>=0
        sources=[]
        if context['method'].startswith('ms_'):
            raw=context['upstream_raw_context']
            raw_text='\n\n'.join(raw) if isinstance(raw,list) else raw
            raw_sources={}
            for row in context['upstream_raw_records'].get('sources',[]):
                short_id=str(row['id'])
                p=provenance[by_short[short_id]['input_id']]
                assert hashlib.sha256(row['text'].encode()).hexdigest()==p['text_sha256']
                raw_sources[short_id]={'text':row['text'],'provenance':p}
                if context['method']=='ms_local':assert row['text'] in raw_text, 'source absent from actual raw context'
            if context['method']=='ms_basic' and raw_text:
                parsed=list(csv.DictReader(io.StringIO(raw_text),delimiter='|',escapechar='\\'))
                assert parsed==context['upstream_raw_records'].get('sources',[]), 'Basic raw CSV differs from records'
            expected_tables=adapt(context['upstream_raw_records'],raw_sources)
            flatten=lambda tables:[(t['name'],t['columns'],r) for t in tables for r in t['rows']]
            kept=flatten(context['final_tables'])
            assert kept==flatten(expected_tables)[:len(kept)], 'adaptation is not a whole-row prefix'
            if count:
                assert render(budget_tables(expected_tables,context['budget'],count))==context['final_context']
        for table in context['final_tables']:
            if table['name']!='sources':continue
            assert table['columns']==['id','source','text']
            for row in table['rows']:
                short_id=str(row['id'])
                mapping=by_short[short_id]
                p=provenance[mapping['input_id']]
                assert row['source']==p['title']
                assert hashlib.sha256(row['text'].encode()).hexdigest()==p['text_sha256'], 'source text changed'
                assert len(row['text'].splitlines())==p['end_line']-p['start_line']+1
                sources.append({'short_id':short_id,'text_unit_id':mapping['text_unit_id'],**p})
        assert sources==context['sources']==result['sources'], 'summary sidecar does not match actual context'
        assert len(sources)==context['source_chunks']==result['source_chunks']
        for key in ('final_context_tokens','source_text_tokens','retrieval_compute_seconds','adaptation_seconds','raw_context_tokens'):
            assert result[key]==context[key], 'summary auxiliary field differs: '+key
        if count:
            assert count(context['final_context'])==context['final_context_tokens'], 'token mismatch'
            if context['upstream_raw_context'] is not None:
                raw=context['upstream_raw_context']
                assert count('\n\n'.join(raw) if isinstance(raw,list) else raw)==context['raw_context_tokens']
        rebuilt.append(dict(result,sources=sources))
    assert files=={p.name for p in (OUT/'contexts').glob('*.json')}
    return dict(data,records=rebuilt)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--tokens',action='store_true')
    args=parser.parse_args()
    result=validate(args.tokens)
    print(f'Validated {len(result["records"])} unique actual contexts, exact source bytes and provenance; token_recount={args.tokens}.')
