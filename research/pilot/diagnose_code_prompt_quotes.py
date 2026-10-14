"""Review-only exact candidate for report1147; no online repair or model calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'.cache/pilot/code-prompt-20261013'
OUT=HERE/'results/code-prompt'
NEEDLE='urljoin(httpbin_url, ""/"".join(suffix))'
sha=lambda text:hashlib.sha256(text.encode()).hexdigest()
read=lambda path:json.loads(path.read_text())


def no_network(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'}:
        raise RuntimeError('Offline quote diagnosis forbids networking')


sys.addaudithook(no_network)


def candidate(original):
    assert original.count(NEEDLE)==1
    start=original.index(NEEDLE)
    offsets=[start+i for i,c in enumerate(NEEDLE) if c=='"']
    assert len(offsets)==4
    chosen=set(offsets)
    fixed=''.join(('\\' if i in chosen else '')+c for i,c in enumerate(original))
    return fixed,offsets


def generate():
    state=read(RUN/'summary.json');event=state['events'][-1]
    assert state['status']=='stopped' and state['stop_reason']=='community_report_schema_invalid'
    assert event['sequence']==1147 and event['status']=='validated' and event['http_status']==200
    reply=read(RUN/'response-1147.json')['response']
    original=reply['choices'][0]['message']['content']
    try:json.loads(original)
    except json.JSONDecodeError as e:error={'type':type(e).__name__,'message':e.msg,'line':e.lineno,'column':e.colno,'offset':e.pos}
    else:raise AssertionError('Original must remain invalid JSON')
    fixed,offsets=candidate(original)
    from graphrag.index.operations.summarize_communities.community_reports_extractor import CommunityReportResponse
    from graphrag_llm.utils import structure_completion_response
    import jsonschema
    import probe_runtime
    import code_prompt_json_syntax
    jsonschema.validate(json.loads(fixed),probe_runtime.REPORT_SCHEMA)
    parsed=structure_completion_response(fixed,CommunityReportResponse).model_dump()
    assert NEEDLE in parsed['findings'][1]['explanation']
    assert code_prompt_json_syntax.validated_candidate(original,CommunityReportResponse,probe_runtime.REPORT_SCHEMA) is None
    previous=[e for e in state['events'] if e['workflow']=='create_community_reports' and e['status']=='validated' and e['sequence']!=1147]
    assert len(previous)==171
    result={'status':'stopped_pending_separate_quote_format_authorization',
        'event_sequence':1147,'stopped_utc':state['stopped_utc'],
        'scope':'Offline exact candidate only. Existing policy permits trailing commas only and does not authorize this quote insertion. No online handler or resumption enabled.',
        'request_body_sha256':event['request_body_sha256'],'http_status':200,'finish_reason':reply['choices'][0]['finish_reason'],
        'usage':event['usage'],'supervised_seconds':event['elapsed_seconds'],
        'prior_valid_report_count':len(previous),'report_reply_count_including_invalid':len(previous)+1,
        'previous_reports_with_authorized_format_exception':[1027,1091],
        'original_parser_error':error,'original_content':original,'original_content_sha256':sha(original),
        'candidate_content':fixed,'candidate_content_sha256':sha(fixed),
        'insert_backslash_before_original_character_offsets_zero_based':offsets,
        'inserted_characters':4,'deleted_or_replaced_characters':0,
        'only_change':'Insert one JSON escape backslash before each of the four quote characters in the single exact code fragment. Preserve both original doubled quotes on each side of the slash; do not correct that code text.',
        'decoded_candidate_retains_original_code_fragment':NEEDLE,
        'official_schema_candidate_valid':True,'original_requested_schema_candidate_valid':True,
        'candidate_findings':len(parsed['findings']),
        'approved_tail_comma_policy_returns_no_candidate':True,
        'runtime_repair_enabled':False,'candidate_applied':False,'new_provider_calls':0,
        'original_response_file_sha256':hashlib.sha256((RUN/'response-1147.json').read_bytes()).hexdigest(),
        'original_ledger_sha256':hashlib.sha256((RUN/'summary.json').read_bytes()).hexdigest(),
        'remaining_work':'Separate explicit authorization before applying this candidate; then complete reports, graph embeddings,80 offline Local contexts, frozen scoring and independent reviews.'}
    path=OUT/'schema-1147-diagnosis.json';assert not path.exists()
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    return result


def check():
    r=read(OUT/'schema-1147-diagnosis.json');original=r['original_content']
    fixed,offsets=candidate(original)
    assert sha(original)==r['original_content_sha256'] and sha(fixed)==r['candidate_content_sha256']
    assert fixed==r['candidate_content'] and offsets==r['insert_backslash_before_original_character_offsets_zero_based']
    assert len(fixed)==len(original)+4 and r['deleted_or_replaced_characters']==0
    try:json.loads(original)
    except json.JSONDecodeError:pass
    else:raise AssertionError('Original must remain invalid')
    parsed=json.loads(fixed)
    assert NEEDLE in parsed['findings'][1]['explanation'] and len(parsed['findings'])==5
    assert r['runtime_repair_enabled'] is False and r['candidate_applied'] is False
    assert r['prior_valid_report_count']==171 and r['new_provider_calls']==0
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    r=check() if a.check else generate()
    print(json.dumps({k:r[k] for k in ['event_sequence','prior_valid_report_count','inserted_characters','runtime_repair_enabled','new_provider_calls']}))
