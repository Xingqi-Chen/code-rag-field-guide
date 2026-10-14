"""One approved, hash-bound syntax exception for cached report1027 only."""
import copy
import hashlib

APPROVAL='2026-10-14T01:03:05+00:00'
BODY_SHA='772c169e3e992c302bb33825eadd89e276f021648d6828da46dfa7507ec925e4'
ORIGINAL_SHA='e66818747d132548fee26b344cc8ceb5368cc725e2c3004042d3761171c03127'
CANDIDATE_SHA='85962660862fe848ef86382a291a8e8904cca002acef70a87fc446b18f58f805'
POSITIONS=[1595,2236,2876,3461]
sha=lambda text:hashlib.sha256(text.encode()).hexdigest()


def candidate(original):
    assert sha(original)==ORIGINAL_SHA
    assert all(original[i]==',' for i in POSITIONS)
    result=''.join(c for i,c in enumerate(original) if i not in POSITIONS)
    assert sha(result)==CANDIDATE_SHA
    return result


def apply(runtime,messages,response_format,reply):
    import code_prompt_experiment as variant
    from graphrag_llm.utils import structure_completion_response
    path=variant.RUN/'schema-1027-amendment.json'
    if response_format is None or not path.exists():return reply
    amendment=variant.read(path)
    assert amendment['human_approval_utc']==APPROVAL and amendment['approved_single_format_exception'] is True
    assert amendment['request_body_sha256']==BODY_SHA
    body=variant.probe.generation_payload(variant.transport.normalize_messages(messages),variant.probe.REPORT_SCHEMA)
    if variant.sha_body(body)!=BODY_SHA:return reply
    assert amendment['original_content_sha256']==ORIGINAL_SHA and amendment['candidate_content_sha256']==CANDIDATE_SHA
    assert amendment['removed_character_offsets_zero_based']==POSITIONS
    original=reply['choices'][0]['message']['content']
    fixed=candidate(original)
    structure_completion_response(fixed,response_format)
    result=copy.deepcopy(reply)
    result['choices'][0]['message']['content']=fixed
    # Keep the original cache, response file and provider usage untouched.
    runtime.ledger.setdefault('schema_exception_applications',[]).append({
        'time_utc':variant.transport.now(),'original_event':1027,
        'request_body_sha256':BODY_SHA,'original_content_sha256':ORIGINAL_SHA,
        'candidate_content_sha256':CANDIDATE_SHA,'removed_character_offsets_zero_based':POSITIONS,
        'provider_calls_for_repair':0,'original_cache_unchanged':True})
    runtime.save()
    return result
