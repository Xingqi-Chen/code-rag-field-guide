"""Offline graph audit sampling and extraction-concatenation diagnostics.

No repairs or re-indexing. Parse each reply separately and compare with the
actual official direct concatenation, on both fixed runs. Counts are diagnostic,
not a counterfactual retrieval score or proof of complete extraction.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys

os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
import code_prompt_experiment as variant
from index_artifacts import read_table

ROOT,RUN,OUT,BASE=variant.ROOT,variant.RUN,variant.OUT,variant.BASE
read,write,sha=variant.read,variant.write,variant.sha


def no_network(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'}:
        raise RuntimeError('Offline diagnostics forbid networking')


sys.addaudithook(no_network)


def parse_comparison():
    from graphrag.index.operations.extract_graph.graph_extractor import GraphExtractor,TUPLE_DELIMITER,RECORD_DELIMITER
    parser=GraphExtractor(model=None,prompt='',max_gleanings=0)
    documents=[json.loads(x) for x in (ROOT/'.cache/pilot/input/documents.jsonl').read_text().splitlines()]
    result={}
    for label,run,out in [('default',variant.OLD_RUN,BASE),('code-prompt',RUN,OUT)]:
        diagnostics=read(out/'extraction-format-diagnostics.json')
        grouped={}
        for diagnostic in diagnostics:
            seq=diagnostic['sequence']
            req=read(run/f'request-{seq:02}.json')
            first=req['body']['input'][0]['content'][0]['text']
            reply=read(run/f'response-{seq:02}.json')['response']['choices'][0]['message']['content']
            grouped.setdefault(first,{})[diagnostic['operation']]=(seq,reply)
        rows=[]
        for prompt,pair in grouped.items():
            assert set(pair)=={'extraction_initial','extraction_glean'}
            a,first=pair['extraction_initial'];b,second=pair['extraction_glean']
            matches=[d for d in documents if d['text'].strip() in prompt]
            # Containment is unique for these full frozen chunks; no fuzzy matching.
            assert len(matches)==1,(label,a,len(matches))
            doc=matches[0]
            e1,r1=parser._process_result(first,'x',TUPLE_DELIMITER,RECORD_DELIMITER)
            e2,r2=parser._process_result(second,'x',TUPLE_DELIMITER,RECORD_DELIMITER)
            ec,rc=parser._process_result(first+second,'x',TUPLE_DELIMITER,RECORD_DELIMITER)
            key=lambda frame:Counter(json.dumps(row,sort_keys=True) for row in frame.to_dict('records'))
            missing_e=(key(e1)+key(e2))-key(ec)
            missing_r=(key(r1)+key(r2))-key(rc)
            rows.append({'input_id':doc['id'],'title':doc['title'],'initial_sequence':a,'glean_sequence':b,
                'initial_entities':len(e1),'initial_relations':len(r1),'glean_entities':len(e2),'glean_relations':len(r2),
                'concatenated_entities':len(ec),'concatenated_relations':len(rc),
                'entity_record_count_gap':len(e1)+len(e2)-len(ec),
                'relationship_record_count_gap':len(r1)+len(r2)-len(rc),
                'first_ends_expected':first.rstrip().endswith('<|COMPLETE|>'),
                'glean_starts_record_delimiter':second.lstrip().startswith('##'),
                'missing_entity_records':[{'record':json.loads(k),'count':v} for k,v in missing_e.items()],
                'changed_or_missing_relation_records':[{'record':json.loads(k),'count':v} for k,v in missing_r.items()],
                'initial_text_sha256':hashlib.sha256(first.encode()).hexdigest(),
                'glean_text_sha256':hashlib.sha256(second.encode()).hexdigest()})
        assert len(rows)==114
        rows.sort(key=lambda x:x['initial_sequence'])
        result[label]={'chunks':114,'chunks_with_entity_record_count_gap':sum(r['entity_record_count_gap']>0 for r in rows),
            'chunks_with_relationship_record_count_gap':sum(r['relationship_record_count_gap']>0 for r in rows),
            'entity_record_count_gap':sum(r['entity_record_count_gap'] for r in rows),
            'relationship_record_count_gap':sum(r['relationship_record_count_gap'] for r in rows),'rows':rows}
    write(OUT/'concatenation-diagnostics.json',{'scope':'Existing replies only. Separately parsed counts versus the unchanged official first+glean parse. Changed relation records may reflect appended marker/weight parsing; this is not repaired graph quality or retrieval.',
        'runs':result,'new_model_calls':0})
    print(json.dumps({label:{k:v for k,v in r.items() if k!='rows'} for label,r in result.items()}))


def sample():
    result={}
    for label,base in [('default',BASE),('code-prompt',OUT)]:
        units={u['ms_text_unit_id']:u for u in read(BASE/'index/text-unit-provenance.json')}
        chosen={}
        for kind in ['entities','relationships']:
            rows=read_table(base/f'index/{kind}.json')
            ordered=sorted(rows,key=lambda r:hashlib.sha256(f"20261012:{kind}:{r['id']}".encode()).hexdigest())
            chosen[kind]=[{'record':r,'sources':[{'title':units[u]['title'],'input_id':units[u]['id']} for u in r['text_unit_ids']],
                'sample_hash':hashlib.sha256(f"20261012:{kind}:{r['id']}".encode()).hexdigest()} for r in ordered[:20]]
        result[label]=chosen
    write(OUT/'quality-sample.json',{'seed':20261012,'selection':'Hash-sort seed:table:id, first 20 entities and 20 relationships per graph; no questions/gold used.',
        'scope':'Small, independent samples of two fixed graph outputs; not matched pairs or human whole-graph precision. UUIDs differ across independent index runs.',
        'rubric':{'supported':'Linked source supports identifiable symbol/concept and main statement; relation endpoints and stated relation supported.',
            'partial_or_ambiguous':'Some support, but unresolved identity/binding or omitted condition prevents exact claim.',
            'unsupported':'Main claim contradicts or lacks support in linked sources.',
            'separate_flags':['exact_code_symbol','visible_direction_supported','dynamic_target_overclaim','source_link_missing','name_changed_or_ambiguous']},'samples':result})
    print('Frozen hash-selected 20 entities and 20 relationships from each graph for source audit.')


def witnesses():
    """Export the same four already-selected source chunks, never select by new outcome."""
    assert read(RUN/'summary.json')['status']=='index_complete'
    variant.check_frozen()
    previous=read(BASE/'failure-analysis/extraction-witnesses.json')
    diagnostics=read(OUT/'extraction-format-diagnostics.json')
    events={e['sequence']:e for e in read(OUT/'execution.json')['events']}
    units=[]
    for old in previous['units']:
        unit={k:v for k,v in old.items() if k not in {'replies','prompt_source_check'}}
        replies=[]
        for d in diagnostics:
            seq=d['sequence'];request=read(RUN/f'request-{seq:02}.json')
            body=request['body'];prompt=body['input'][0]['content'][0]['text']
            if old['source_text'].strip() not in prompt:continue
            response=read(RUN/f'response-{seq:02}.json')['response']
            choice=response['choices'][0];content=choice['message']['content']
            assert hashlib.sha256(content.encode()).hexdigest()==d['normalized_visible_output_sha256']
            assert variant.probe.digest(variant.probe.canonical(body).encode())==events[seq]['request_body_sha256']
            replies.append({'sequence':seq,'operation':d['operation'],
                'normalized_finish_reason':choice['finish_reason'],'content':content,
                'content_sha256':hashlib.sha256(content.encode()).hexdigest(),
                'request_body':body,'request_body_sha256':events[seq]['request_body_sha256']})
        assert len(replies)==2 and {r['operation'] for r in replies}=={'extraction_initial','extraction_glean'}
        unit.update(replies=replies,prompt_source_check='Frozen code prompt includes the same exact source_text.strip(); no source positions injected.')
        units.append(unit)
    write(OUT/'extraction-witnesses.json',{'selection':'The same four previously published default-run chunks for Q01/Q07/Q13/G02; selected before viewing new results, not a representative sample.',
        'units':units,'new_model_calls':0})
    print('Exported four unchanged source witnesses and eight complete new extraction request/reply pairs.')


def witness_parser_check(check=False):
    """The four completed witnesses can be checked before the full index ends."""
    from graphrag.index.operations.extract_graph.graph_extractor import GraphExtractor,TUPLE_DELIMITER,RECORD_DELIMITER
    parser=GraphExtractor(model=None,prompt='',max_gleanings=0)
    path=OUT/'preindex-fixed-witnesses.json';rows=[]
    for unit in read(path)['units']:
        first,second=[r['content'] for r in sorted(unit['replies'],key=lambda r:r['sequence'])]
        e1,r1=parser._process_result(first,'x',TUPLE_DELIMITER,RECORD_DELIMITER)
        e2,r2=parser._process_result(second,'x',TUPLE_DELIMITER,RECORD_DELIMITER)
        ec,rc=parser._process_result(first+second,'x',TUPLE_DELIMITER,RECORD_DELIMITER)
        rows.append({'source_title':unit.get('title',unit.get('source_title')),
            'initial_sequence':min(r['sequence'] for r in unit['replies']),
            'initial_entity_records':len(e1),'glean_entity_records':len(e2),'concatenated_entity_records':len(ec),
            'entity_gap':len(e1)+len(e2)-len(ec),
            'initial_relationship_records':len(r1),'glean_relationship_records':len(r2),'concatenated_relationship_records':len(rc),
            'relationship_gap':len(r1)+len(r2)-len(rc)})
    result={'scope':'Four fixed completed extraction witnesses, official unchanged parser invoked offline. Not a repaired graph or retrieval score.',
        'new_model_calls':0,'source_witness_sha256':sha(path),'rows':rows}
    destination=OUT/'preindex-official-parser-check.json'
    if check:assert result==read(destination)
    else:write(destination,result)
    print('Verified four fixed witnesses with the unchanged official parser; no model calls.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['parse','sample','witnesses','witness-parse-check']);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    assert not args.check or args.action=='witness-parse-check'
    if args.action=='parse':parse_comparison()
    elif args.action=='sample':sample()
    elif args.action=='witnesses':witnesses()
    else:witness_parser_check(args.check)
