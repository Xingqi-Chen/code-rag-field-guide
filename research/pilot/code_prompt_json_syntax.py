"""Approved run-scoped removal of trailing JSON commas, never semantic repair."""
import copy
import hashlib
import json

APPROVAL='2026-10-14T01:27:36+00:00'
POLICY={'human_approval_utc':APPROVAL,'scope':'This fixed code-prompt run only',
    'allowed_change':'Delete commas outside strings whose next non-whitespace character is an object or array closing delimiter.',
    'require_original_schema':True,'preserve_all_string_tokens':True,
    'retain_original_response_and_cache':True,'resend_complete_response':False,
    'retain_original_candidate_and_offsets_per_reply':True,'arbitrary_json_or_semantic_repair':False}
sha=lambda text:hashlib.sha256(text.encode()).hexdigest()


def candidate(text):
    in_string=False;escaped=False;positions=[];string_tokens=[];start=None
    for i,char in enumerate(text):
        if in_string:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':
                in_string=False;string_tokens.append(text[start:i+1])
            continue
        if char=='"':in_string=True;start=i
        elif char==',':
            j=i+1
            while j<len(text) and text[j] in ' \t\r\n':j+=1
            if j<len(text) and text[j] in '}]':positions.append(i)
    if in_string or escaped:return text,[],string_tokens
    removed=set(positions)
    return ''.join(c for i,c in enumerate(text) if i not in removed),positions,string_tokens


def validated_candidate(original,response_format,schema):
    # Valid JSON is always left to the unchanged upstream validation path.
    try:json.loads(original)
    except json.JSONDecodeError:pass
    else:return None
    fixed,positions,strings=candidate(original)
    if not positions:return None
    from graphrag_llm.utils import structure_completion_response
    import jsonschema
    def unique_fields(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('Duplicate fields make a format repair ambiguous')
            value[key]=item
        return value
    try:
        parsed=json.loads(fixed,object_pairs_hook=unique_fields)
        jsonschema.validate(parsed,schema)
        structure_completion_response(fixed,response_format)
    except (json.JSONDecodeError,jsonschema.ValidationError,ValueError,TypeError):return None
    assert candidate(fixed)[2]==strings
    return fixed,positions


def apply(runtime,messages,response_format,reply):
    import code_prompt_experiment as variant
    path=variant.RUN/'json-tail-comma-amendment.json'
    if response_format is None or not path.exists():return reply
    amendment=variant.read(path);assert amendment['policy']==POLICY
    original=reply['choices'][0]['message']['content']
    result=validated_candidate(original,response_format,variant.probe.REPORT_SCHEMA)
    if result is None:return reply  # Any other defect still fails upstream.
    fixed,positions=result
    normalized=variant.transport.normalize_messages(messages)
    body=variant.probe.generation_payload(normalized,variant.probe.REPORT_SCHEMA)
    body_sha=variant.sha_body(body)
    matches=[e for e in runtime.ledger['events'] if e['request_body_sha256']==body_sha and e['status']=='validated']
    assert len(matches)==1
    event=matches[0];seq=event['sequence']
    assert event['service']=='generation' and event['workflow']=='create_community_reports'
    assert seq>=1091,'Earlier report1027 uses its historical exact-response exception'
    key=variant.transport.completion_key(normalized,variant.probe.REPORT_SCHEMA)
    cache=variant.RUN/'completion-cache'/f'{key}.json'
    assert variant.read(cache)['response']==reply
    response=variant.RUN/f'response-{seq:02}.json'
    assert variant.read(response)['response']==reply
    record={'original_event':seq,'request_body_sha256':body_sha,'human_approval_utc':APPROVAL,
        'original_content':original,'original_content_sha256':sha(original),
        'candidate_content':fixed,'candidate_content_sha256':sha(fixed),
        'removed_character_offsets_zero_based':positions,'all_string_tokens_unchanged':True,
        'original_schema_validated':True,'provider_calls_for_repair':0,'original_usage':event['usage'],
        'original_response_file_sha256':variant.sha(response),'original_cache_sha256':variant.sha(cache),
        'scope':'Only listed commas removed; original model text, cache and usage retained. No model resend.'}
    relative=f'json-syntax-repairs/event-{seq}.json'
    for directory in [variant.RUN,variant.OUT]:
        target=directory/relative
        if target.exists():assert variant.read(target)==record
        else:variant.write(target,record)
    meta={k:v for k,v in record.items() if k not in {'original_content','candidate_content'}}
    meta.update(evidence_file=relative,evidence_sha256=variant.sha(variant.OUT/relative))
    repairs=runtime.ledger.setdefault('json_syntax_repairs',[])
    existing=[r for r in repairs if r['original_event']==seq]
    if existing:assert existing==[meta]
    else:repairs.append(meta)
    runtime.ledger.setdefault('json_syntax_repair_applications',[]).append({
        'original_event':seq,'time_utc':variant.transport.now(),'candidate_content_sha256':sha(fixed),
        'provider_calls_for_repair':0})
    runtime.save()
    copied=copy.deepcopy(reply);copied['choices'][0]['message']['content']=fixed
    return copied
