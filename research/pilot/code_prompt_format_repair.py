"""Run-authorized deterministic JSON syntax repairs; preserve original replies."""
import copy
import hashlib
import json

APPROVAL='2026-10-14T01:51:30+00:00'
POLICY={'human_approval_utc':APPROVAL,'scope':'This fixed code-prompt run only, from retained report1147.',
    'authorization':'Apply the reviewed1147 candidate and subsequent similar deterministic minimal JSON-format repairs without changing text semantics or field values.',
    'implemented_changes':['Escape unescaped double quotes within balanced single-backtick inline code spans inside a JSON string; preserve doubled quotes.',
        'Remove trailing commas outside strings before an object or array closing delimiter.'],
    'require_original_schema':True,'retain_original_response_and_cache':True,'resend_complete_response':False,
    'retain_original_candidate_and_exact_edits_per_reply':True,
    'reject_ambiguous_content_missing_fields_type_or_semantic_changes':True}
sha=lambda text:hashlib.sha256(text.encode()).hexdigest()


def unambiguous_json(text):
    def object_pairs(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate field is ambiguous')
            result[key]=value
        return result
    return json.loads(text,object_pairs_hook=object_pairs)


def apply_edits(original,edits):
    result=[];cursor=0
    for edit in sorted(edits,key=lambda e:e['offset']):
        position=edit['offset'];assert cursor<=position<=len(original)
        assert original[position:position+len(edit['delete'])]==edit['delete']
        result.extend([original[cursor:position],edit['insert']]);cursor=position+len(edit['delete'])
    result.append(original[cursor:]);return ''.join(result)


def candidate(original):
    """Only syntax with explicit inline-code boundaries; no guessed field values."""
    in_string=False;escaped=False;i=0;edits=[];spans=[]
    while i<len(original):
        c=original[i]
        if not in_string:
            if c=='"':in_string=True
            i+=1;continue
        if escaped:escaped=False;i+=1;continue
        if c=='\\':escaped=True;i+=1;continue
        if c=='"':in_string=False;i+=1;continue
        if c!='`':i+=1;continue
        end=original.find('`',i+1)
        if end<0 or end==i+1 or any(x in original[i+1:end] for x in ['\n','\r']):
            return None  # Unbalanced/multiline/fenced code is not this deterministic rule.
        fragment=original[i+1:end]
        # Do not cross apparent JSON field/container boundaries inside malformed text.
        if '":' in fragment or '\" :' in fragment:return None
        quote_positions=[];j=i+1;code_escaped=False
        while j<end:
            if code_escaped:code_escaped=False
            elif original[j]=='\\':code_escaped=True
            elif original[j]=='"':quote_positions.append(j)
            j+=1
        if quote_positions:
            edits.extend({'offset':j,'delete':'','insert':'\\','reason':'escape_quote_in_explicit_inline_code'} for j in quote_positions)
            spans.append({'start':i,'end_exclusive':end+1,'original':original[i:end+1],
                'quote_offsets':quote_positions})
        i=end+1
    if in_string or escaped:return None
    interim=apply_edits(original,edits)
    from code_prompt_json_syntax import candidate as trailing
    _,commas,_=trailing(interim)
    # Map intermediate positions back to immutable original character positions.
    inserted={e['offset'] for e in edits};mapping=[]
    for position in range(len(original)):
        if position in inserted:mapping.append(None)
        mapping.append(position)
    for position in commas:
        old=mapping[position];assert old is not None and original[old]==','
        edits.append({'offset':old,'delete':',','insert':'','reason':'trailing_comma_outside_string'})
    if not edits:return None
    fixed=apply_edits(original,edits)
    try:unambiguous_json(fixed)
    except (json.JSONDecodeError,ValueError):return None
    return fixed,sorted(edits,key=lambda e:e['offset']),spans


def validated_candidate(original,response_format,schema):
    try:json.loads(original)
    except json.JSONDecodeError:pass
    else:return None
    result=candidate(original)
    if result is None:return None
    fixed,edits,spans=result
    import jsonschema
    from graphrag_llm.utils import structure_completion_response
    try:
        jsonschema.validate(unambiguous_json(fixed),schema)
        structure_completion_response(fixed,response_format)
    except (json.JSONDecodeError,jsonschema.ValidationError,ValueError,TypeError):return None
    # Every chosen edit must be necessary for syntactic validity within this rule.
    for index in range(len(edits)):
        try:json.loads(apply_edits(original,edits[:index]+edits[index+1:]))
        except json.JSONDecodeError:pass
        else:return None
    return fixed,edits,spans


def apply(runtime,messages,response_format,reply):
    import code_prompt_experiment as variant
    path=variant.RUN/'json-format-amendment.json'
    if response_format is None or not path.exists():return reply
    amendment=variant.read(path);assert amendment['policy']==POLICY
    original=reply['choices'][0]['message']['content']
    result=validated_candidate(original,response_format,variant.probe.REPORT_SCHEMA)
    if result is None:return reply
    fixed,edits,spans=result
    normalized=variant.transport.normalize_messages(messages)
    body=variant.probe.generation_payload(normalized,variant.probe.REPORT_SCHEMA);body_sha=variant.sha_body(body)
    matches=[e for e in runtime.ledger['events'] if e['request_body_sha256']==body_sha and e['status']=='validated']
    assert len(matches)==1
    event=matches[0];sequence=event['sequence']
    assert sequence>=1147 and event['workflow']=='create_community_reports' and event['service']=='generation'
    cache=variant.RUN/'completion-cache'/f'{variant.transport.completion_key(normalized,variant.probe.REPORT_SCHEMA)}.json'
    response=variant.RUN/f'response-{sequence:02}.json'
    assert variant.read(cache)['response']==variant.read(response)['response']==reply
    if sequence==1147:
        diagnosis=variant.read(variant.OUT/'schema-1147-diagnosis.json')
        assert sha(original)==diagnosis['original_content_sha256'] and sha(fixed)==diagnosis['candidate_content_sha256']
        assert [e['offset'] for e in edits]==diagnosis['insert_backslash_before_original_character_offsets_zero_based']
    record={'original_event':sequence,'request_body_sha256':body_sha,'human_approval_utc':APPROVAL,
        'original_content':original,'original_content_sha256':sha(original),'candidate_content':fixed,'candidate_content_sha256':sha(fixed),
        'exact_edits':edits,'inline_code_spans':spans,'each_edit_necessary_for_json_validity':True,
        'original_schema_validated':True,'provider_calls_for_repair':0,'original_usage':event['usage'],
        'original_response_file_sha256':variant.sha(response),'original_cache_sha256':variant.sha(cache),
        'scope':'Only deterministic syntax edits; retain original model text and doubled code quotes. Original invalid JSON has no parsed value to compare. No semantic correction or resend.'}
    relative=f'json-format-repairs/event-{sequence}.json'
    for directory in [variant.RUN,variant.OUT]:
        target=directory/relative
        if target.exists():assert variant.read(target)==record
        else:variant.write(target,record)
    meta={k:v for k,v in record.items() if k not in {'original_content','candidate_content'}}
    meta.update(evidence_file=relative,evidence_sha256=variant.sha(variant.OUT/relative))
    repairs=runtime.ledger.setdefault('json_format_repairs',[]);existing=[r for r in repairs if r['original_event']==sequence]
    if existing:assert existing==[meta]
    else:repairs.append(meta)
    runtime.ledger.setdefault('json_format_repair_applications',[]).append({'original_event':sequence,
        'time_utc':variant.transport.now(),'candidate_content_sha256':sha(fixed),'provider_calls_for_repair':0})
    runtime.save();copied=copy.deepcopy(reply);copied['choices'][0]['message']['content']=fixed
    return copied
