"""Resume after the approved, single cached-report1027 syntax exception."""
import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys

import code_prompt_schema_exception as exception
import resume_code_prompt_transient as current

variant,bounded=current.variant,current.bounded


def prepare(approved,approval_utc):
    assert approved and approval_utc==exception.APPROVAL
    variant.configure();variant.check_frozen()
    runtime=variant.CodeRuntime(offline=True)
    try:
        s=runtime.ledger;e=s['events'][-1]
        assert s['status']=='stopped' and s['stop_reason']=='community_report_schema_invalid'
        assert e['sequence']==1027 and e['status']=='validated' and e['http_status']==200
        assert e['request_body_sha256']==exception.BODY_SHA
        assert s['limits']==variant.read(variant.RUN/'generation-cap-amendment.json')['new_limits']
        assert s['timeout_retry_policy']==current.POLICY and s['wall_deadline_removed']
        count=bounded.verify_successful_cache(runtime)
        assert count==1018
        request=variant.read(variant.RUN/'request-1027.json')['body']
        response=variant.read(variant.RUN/'response-1027.json')['response']
        assert variant.sha_body(request)==exception.BODY_SHA
        original=response['choices'][0]['message']['content']
        fixed=exception.candidate(original)
        from graphrag.index.operations.summarize_communities.community_reports_extractor import CommunityReportResponse
        from graphrag_llm.utils import structure_completion_response
        structured=structure_completion_response(fixed,CommunityReportResponse)
        assert len(structured.findings)==5
        messages=[{'role':m['role'],'content':m['content'][0]['text']} for m in request['input']]
        key=variant.transport.completion_key(messages,variant.probe.REPORT_SCHEMA)
        cache=variant.RUN/'completion-cache'/f'{key}.json'
        assert variant.read(cache)['response']==response
        number=len(s['recoveries'])+1
        snapshot=variant.RUN/f'stopped-{number:02}.json'
        partial=variant.RUN/f'partial-index-at-stop-{number:02}'
        assert number==11 and not snapshot.exists() and not partial.exists()
        amendment={'human_approval_utc':approval_utc,'applied_utc':variant.transport.now(),
            'approved_single_format_exception':True,'event':1027,'request_body_sha256':exception.BODY_SHA,
            'original_content_sha256':exception.ORIGINAL_SHA,'candidate_content_sha256':exception.CANDIDATE_SHA,
            'removed_character_offsets_zero_based':exception.POSITIONS,
            'original_response_file_sha256':variant.sha(variant.RUN/'response-1027.json'),
            'original_completion_cache_sha256':variant.sha(cache),'original_usage':e['usage'],
            'runtime_source_sha256':{Path(module.__file__).name:variant.sha(Path(module.__file__))
                for module in [variant,exception,sys.modules[__name__]]},
            'operation':'In-memory copy returned from the exact cached reply; delete four known trailing commas only. Original files retained.',
            'successful_generation_caches_verified':count,'imported_vectors_verified':134,
            'new_provider_calls_for_repair':0,'other_limits_and_policy_unchanged':True,
            'not_general_json_or_semantic_repair':True,'official_schema_validated':True}
        assert not (variant.RUN/'schema-1027-amendment.json').exists()
        variant.write(snapshot,s)
        os.rename(variant.RUN/'output',partial)
        s.setdefault('schema_format_exceptions',[]).append(amendment)
        s['recoveries'].append({'time_utc':amendment['applied_utc'],'event':1027,
            'reason':'approved_single_cached_report_syntax_exception','authorization_utc':approval_utc,
            'response_reused_without_resending':True,'successful_responses_reused':count,
            'snapshot':snapshot.name,'new_calls_for_recovery':0,'request_body_sha256':exception.BODY_SHA,
            'original_content_sha256':exception.ORIGINAL_SHA,'candidate_content_sha256':exception.CANDIDATE_SHA})
        s['verified_resume_ready']=True;s['verified_resume_number']=number
        runtime.save()
        variant.write(variant.RUN/'schema-1027-amendment.json',amendment)
        variant.write(variant.OUT/'schema-1027-amendment.json',amendment)
        print(f'Approved report1027 syntax overlay ready;{count} original caches verified; no replay.',flush=True)
    finally:runtime._lock_file.close()


async def worker():
    variant.configure();variant.check_frozen();current.install()
    s=variant.read(variant.RUN/'summary.json')
    assert s['verified_resume_ready'] and s['verified_resume_number']==11
    assert s['events'][-1]['sequence']==1027 and s['events'][-1]['status']=='validated'
    assert s['recoveries'][-1]['response_reused_without_resending']
    return await variant.full_index.index(resume=True)


def controller():
    result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker'])
    current.install()
    while True:
        state=variant.read(variant.RUN/'summary.json')
        if result.returncode==0 and state['status']=='index_complete':return 0
        if state['status']!='stopped' or not bounded.prepare_recovery():return 1
        result=subprocess.run([sys.executable,str(Path(current.__file__).resolve()),'resume-worker'])
        if not bounded.bind_retry_event():return 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','continue','worker'])
    p.add_argument('--user-approved-single-format-exception',action='store_true');p.add_argument('--human-approval-utc')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.user_approved_single_format_exception,a.human_approval_utc)
    elif a.action=='worker':sys.exit(asyncio.run(worker()))
    else:sys.exit(controller())
