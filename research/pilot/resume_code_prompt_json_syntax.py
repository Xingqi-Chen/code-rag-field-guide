"""Continue from1091 under the explicitly approved tail-comma-only policy."""
import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys

import code_prompt_json_syntax as syntax
import resume_code_prompt_transient as current

variant,bounded=current.variant,current.bounded


def prepare(approved,approval_utc):
    assert approved and approval_utc==syntax.APPROVAL
    variant.configure();variant.check_frozen()
    runtime=variant.CodeRuntime(offline=True)
    try:
        s=runtime.ledger;e=s['events'][-1]
        assert s['status']=='stopped' and s['stop_reason']=='community_report_schema_invalid'
        assert e['sequence']==1091 and e['status']=='validated' and e['http_status']==200
        diagnosis=variant.read(variant.OUT/'schema-1091-diagnosis.json')
        assert e['request_body_sha256']==diagnosis['request_body_sha256']
        assert s['limits']==variant.read(variant.RUN/'generation-cap-amendment.json')['new_limits']
        assert s['timeout_retry_policy']==current.POLICY and s['wall_deadline_removed']
        count=bounded.verify_successful_cache(runtime);assert count==1082
        reply=variant.read(variant.RUN/'response-1091.json')['response']
        from graphrag.index.operations.summarize_communities.community_reports_extractor import CommunityReportResponse
        result=syntax.validated_candidate(reply['choices'][0]['message']['content'],CommunityReportResponse,variant.probe.REPORT_SCHEMA)
        assert result==(diagnosis['candidate_content'],diagnosis['removed_character_offsets_zero_based'])
        number=len(s['recoveries'])+1;assert number==12
        snapshot=variant.RUN/f'stopped-{number:02}.json';partial=variant.RUN/f'partial-index-at-stop-{number:02}'
        assert not snapshot.exists() and not partial.exists() and not (variant.RUN/'json-tail-comma-amendment.json').exists()
        amendment={'human_approval_utc':approval_utc,'applied_utc':variant.transport.now(),'policy':syntax.POLICY,
            'trigger_event':1091,'successful_generation_caches_verified':count,'imported_vectors_verified':134,
            'new_provider_calls_for_repair':0,'limits_before':s['limits'],'limits_after':s['limits'],
            'transient_retry_policy_unchanged':True,'total_deadline_reintroduced':False,
            'runtime_source_sha256':{Path(module.__file__).name:variant.sha(Path(module.__file__))
                for module in [variant,syntax,sys.modules[__name__]]}}
        variant.write(snapshot,s);os.rename(variant.RUN/'output',partial)
        s['json_tail_comma_policy']=amendment
        s['recoveries'].append({'time_utc':amendment['applied_utc'],'event':1091,
            'reason':'authorized_run_json_tail_comma_policy','authorization_utc':approval_utc,
            'successful_response_retained':True,'successful_responses_reused':count,
            'snapshot':snapshot.name,'new_calls_for_recovery':0,'request_body_sha256':e['request_body_sha256']})
        s['verified_resume_ready']=True;s['verified_resume_number']=number
        runtime.save()
        variant.write(variant.RUN/'json-tail-comma-amendment.json',amendment)
        variant.write(variant.OUT/'json-tail-comma-amendment.json',amendment)
        print(f'Approved tail-comma-only policy ready;{count} original replies verified; no resend.',flush=True)
    finally:runtime._lock_file.close()


async def worker():
    variant.configure();variant.check_frozen();current.install()
    s=variant.read(variant.RUN/'summary.json')
    assert s['verified_resume_ready'] and s['verified_resume_number']==12
    assert s['events'][-1]['sequence']==1091 and s['events'][-1]['status']=='validated'
    assert s['recoveries'][-1]['successful_response_retained']
    return await variant.full_index.index(resume=True)


def controller():
    result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker'])
    current.install()
    while True:
        s=variant.read(variant.RUN/'summary.json')
        if result.returncode==0 and s['status']=='index_complete':return 0
        if s['status']!='stopped' or not bounded.prepare_recovery():return 1
        result=subprocess.run([sys.executable,str(Path(current.__file__).resolve()),'resume-worker'])
        if not bounded.bind_retry_event():return 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','continue','worker'])
    p.add_argument('--user-approved-tail-comma-policy',action='store_true');p.add_argument('--human-approval-utc')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.user_approved_tail_comma_policy,a.human_approval_utc)
    elif a.action=='worker':sys.exit(asyncio.run(worker()))
    else:sys.exit(controller())
