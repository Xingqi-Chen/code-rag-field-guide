"""Offline diagnosis of selected stopped reports; never modifies run/cache data.

The candidate removes only commas outside strings immediately before a JSON
object/array closing delimiter. It is a review artifact, not an enabled repair.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'


def no_network(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'}:
        raise RuntimeError('Schema diagnosis forbids networking')


sys.addaudithook(no_network)
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
RUN=ROOT/'.cache/pilot/code-prompt-20261013'
OUT=HERE/'results/code-prompt'
sha=lambda text:hashlib.sha256(text.encode()).hexdigest()
read=lambda path:json.loads(path.read_text())


def trailing_comma_candidate(text):
    in_string=False;escaped=False;positions=[]
    for i,char in enumerate(text):
        if in_string:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':in_string=False
            continue
        if char=='"':in_string=True
        elif char==',':
            j=i+1
            while j<len(text) and text[j] in ' \t\r\n':j+=1
            if j<len(text) and text[j] in '}]':positions.append(i)
    assert not in_string and not escaped
    removed=set(positions)
    return ''.join(char for i,char in enumerate(text) if i not in removed),positions


def validate_report(text):
    from graphrag.index.operations.summarize_communities.community_reports_extractor import CommunityReportResponse
    from graphrag_llm.utils import structure_completion_response
    return structure_completion_response(text,CommunityReportResponse).model_dump()


def generate(sequence=1027):
    state=read(RUN/'summary.json')
    assert state['status']=='stopped' and state['stop_reason']=='community_report_schema_invalid'
    event=state['events'][-1]
    assert event['sequence']==sequence and event['status']=='validated' and event['http_status']==200
    reply=read(RUN/f'response-{sequence}.json')['response']
    original=reply['choices'][0]['message']['content']
    try:validate_report(original)
    except json.JSONDecodeError as exc:
        error={'type':type(exc).__name__,'message':exc.msg,'line':exc.lineno,'column':exc.colno,'offset':exc.pos}
    else:raise AssertionError('Expected the unchanged official parser to reject the selected report')
    candidate,positions=trailing_comma_candidate(original)
    assert len(positions)==4
    parsed=validate_report(candidate)
    assert len(parsed['findings'])==5
    previous=[];previous_exceptions=[]
    for e in state['events']:
        if e['workflow']=='create_community_reports' and e['sequence']!=sequence and e['status']=='validated':
            text=read(RUN/f"response-{e['sequence']:02}.json")['response']['choices'][0]['message']['content']
            if e['sequence']==1027 and sequence>1027:
                amendment=read(RUN/'schema-1027-amendment.json');old=read(OUT/'schema-1027-diagnosis.json')
                assert amendment['approved_single_format_exception'] and sha(text)==amendment['original_content_sha256']
                text=old['candidate_content'];assert sha(text)==amendment['candidate_content_sha256']
                previous_exceptions.append(1027)
            validate_report(text)
            previous.append(e['sequence'])
    result={'status':'stopped_pending_reviewed_format_exception',
        'scope':'Diagnosis and candidate only; original response/cache/ledger untouched, no retry or parser amendment enabled.',
        'event_sequence':sequence,'request_body_sha256':event['request_body_sha256'],
        'stopped_utc':state['stopped_utc'],'http_status':200,'finish_reason':reply['choices'][0]['finish_reason'],
        'usage':event['usage'],'supervised_seconds':event['elapsed_seconds'],
        'successful_prior_report_schemas':previous,'prior_valid_report_count':len(previous),
        'previous_reports_with_already_authorized_format_exception':previous_exceptions,
        'transport_success_is_not_schema_success':True,
        'official_parser_error':error,'original_content':original,'original_content_sha256':sha(original),
        'candidate_content':candidate,'candidate_content_sha256':sha(candidate),
        'removed_character_offsets_zero_based':positions,
        'only_change':'Delete four commas outside JSON strings, each immediately before an object closing brace after whitespace.',
        'official_schema_candidate_valid':True,'candidate_findings':len(parsed['findings']),
        'source_and_model_calls':{'new_generation':0,'new_embedding':0},
        'runtime_repair_enabled':False,'authorization_required_for_execution_change':True,
        'remaining_work':'Resume community reports under an explicitly accepted format exception, then embeddings,80 offline Local contexts, scoring, independent reviews and publication.'}
    path=OUT/f'schema-{sequence}-diagnosis.json'
    assert not path.exists(),'Never replace a published diagnosis'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    return result


def check(sequence=1027):
    result=read(OUT/f'schema-{sequence}-diagnosis.json')
    original=result['original_content'];candidate,positions=trailing_comma_candidate(original)
    assert result['original_content_sha256']==sha(original)
    assert candidate==result['candidate_content'] and result['candidate_content_sha256']==sha(candidate)
    assert positions==result['removed_character_offsets_zero_based'] and len(positions)==4
    assert all(original[i]==',' for i in positions)
    assert len(json.loads(candidate)['findings'])==5
    assert result['runtime_repair_enabled'] is False
    assert result['prior_valid_report_count']=={1027:51,1091:115}[sequence]
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--event',type=int,choices=[1027,1091],default=1027);a=p.parse_args()
    r=check(a.event) if a.check else generate(a.event)
    print(json.dumps({'sequence':r['event_sequence'],'prior_valid_report_count':r['prior_valid_report_count'],
        'candidate_schema_valid':r['official_schema_candidate_valid'],'removed_commas':len(r['removed_character_offsets_zero_based']),
        'runtime_repair_enabled':False,'new_provider_calls':0}))
