"""Export an allowlisted, credential-free execution record and inspectable graph."""
from collections import Counter
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics

import probe_runtime as probe

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'.cache/pilot/full-20261012'
from result_paths import OUT


def write(name,obj):
    path=OUT/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def seconds(start,end):
    return (datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()


def main(initial_prompts=None):
    import pandas as pd
    state=json.loads((RUN/'summary.json').read_text())
    assert state['status'] in {'stopped','index_complete','retrieval_complete','generation_complete'}
    partial=state['status']=='stopped'
    public_keys=['run_id','created_utc','started_utc','limits','status','prior_probe_reserved',
        'prior_probe_elapsed_seconds','index_generation_attempts','feature_generation_attempts',
        'embedding_attempts','generation_input_tokens','embedding_reserved_tokens',
        'logical_completion_calls','completion_cache_hits','logical_embedding_calls',
        'embedding_cache_items','imported_successful_probe_cache','source_commit','workflows',
        'executions','recoveries','index_elapsed_seconds','index_finished_utc',
        'retrieval_finished_utc','generation_finished_utc','stopped_utc','stop_reason',
        'window_started_utc','window_deadline_utc','execution_windows','evaluation_authorization','host_interruption_timing',
        'schema_format_exceptions','schema_exception_applications']
    public={k:state[k] for k in public_keys if k in state}
    event_keys=['sequence','service','phase','workflow','input_tokens','items','status',
        'request_body_sha256','started_utc','source_commit','supervisor_reason','worker_exit',
        'elapsed_seconds','http_status','error_category','response_format','validation_reason',
        'usage','visible_output_common_tokens','requested_output_limit_exceeded',
        'worker_source_sha256','response_byte_limit','response_bytes','request_dispatched','policy_checkpoint','code_prompt_source_sha256',
        'validation_stage','validated_utc','original_ledger_status',
        'retry_after_seconds','retry_not_before_utc','retry_after_invalid']
    public['events']=[{k:e[k] for k in event_keys if k in e} for e in state['events']]
    classifications=Counter()
    if initial_prompts is None:
        initial_prompts={probe.prompt_values()['GRAPH_EXTRACTION_PROMPT'].format(
            entity_types='organization,person,geo,event',input_text=json.loads(line)['text'].strip())
            for line in (ROOT/'.cache/pilot/input/documents.jsonl').read_text().splitlines()}
    output_diagnostics=[]
    usage_totals=Counter()
    for event in public['events']:
        seq=event['sequence']
        task=json.loads((RUN/f'request-{seq:02}.json').read_text())
        response_path=RUN/f'response-{seq:02}.json'
        envelope=json.loads(response_path.read_text()) if response_path.exists() else {}
        body,reply=task['body'],envelope.get('response',{})
        if task['service']=='embedding':kind='embedding'
        elif event['phase']=='feature':kind='feature'
        elif 'text' in body:kind='community_report'
        elif body['input'][0]['content'][0]['text'] in initial_prompts:
            kind='extraction_glean' if len(body['input'])>1 else 'extraction_initial'
        else:kind='description_summary'
        event['operation']=kind
        classifications[kind]+=1
        if 'usage' in reply:
            for k,v in reply['usage'].items():
                if type(v) is int:usage_totals[task['service']+'_'+k]+=v
        if kind in {'extraction_initial','extraction_glean'} and reply:
            text=reply['choices'][0]['message']['content']
            output_diagnostics.append({'sequence':seq,'operation':kind,
                'ends_with_expected_complete_marker':text.rstrip().endswith('<|COMPLETE|>'),
                'normalized_visible_output_sha256':hashlib.sha256(text.encode()).hexdigest()})
        recovery=next((r for r in state.get('recoveries',[]) if r['event']==seq
                       and r.get('response_reused_without_resending')),None)
        if recovery and recovery.get('reason')=='approved_single_cached_report_syntax_exception':
            event['schema_syntax_exception']={
                'original_content_sha256':recovery['original_content_sha256'],
                'candidate_content_sha256':recovery['candidate_content_sha256'],
                'authorization_utc':recovery['authorization_utc'],
                'note':'Original transport-valid reply retained; four approved trailing commas removed in memory for the unchanged report schema. No resending or usage alteration.'}
        elif recovery:
            event['recovery']=('Complete reply validated offline after executor transport loss and reused without resending; original stale ledger retained.'
                if recovery.get('original_status')=='reserved_before_dispatch' else
                'Complete reply independently validated and reused; original rejection retained.')
            event['usage']=reply['usage']
            event['visible_output_common_tokens']=recovery['visible_output_common_tokens']
            event['requested_output_limit_exceeded']=(reply['usage']['completion_tokens']>2048
                or recovery['visible_output_common_tokens']>2048)
    public['operation_counts']=dict(classifications)
    if any(e.get('request_dispatched') is False for e in public['events']):
        public['provider_dispatch_attempts']=dict(Counter(e['service'] for e in public['events'] if e.get('request_dispatched') is not False))
        public['provider_operation_attempts']=dict(Counter(e['operation'] for e in public['events'] if e.get('request_dispatched') is not False))
        public['non_dispatched_reservations']=[e['sequence'] for e in public['events'] if e.get('request_dispatched') is False]
        public['reservation_note']='Attempt/input caps and operation_counts conservatively retain administrative reservations. provider_dispatch_attempts excludes confirmed never-dispatched reservations. Missing provider responses remain unknown.'
    public['observed_usage_totals']=dict(usage_totals)
    public['known_embedding_input_estimate_usd']=str(Decimal(state['embedding_reserved_tokens'])*Decimal('.13')/1000000)
    public['cost_notes']='Embedding estimate includes prior probes at USD0.13/million input tokens, not a verified invoice. Generation price unknown. Missing usage is unknown, never inferred as zero.'
    public['memory_measurement']='Not measured at user request; upstream zero memory fields are instrumentation placeholders.'
    public['provider_identity']='Requested and reported model name; proxy internal backend mapping not independently verified.'
    public['output_limit_exceedances']=sum(bool(e.get('requested_output_limit_exceeded')) for e in public['events'])
    delays=[e['elapsed_seconds'] for e in public['events'] if 'elapsed_seconds' in e]
    public['request_timing']={'sum_supervised_request_seconds':sum(delays),
        'mean_supervised_request_seconds':statistics.mean(delays) if delays else None,
        'definition':'Client dispatch-to-worker-exit; includes transport and response validation overhead, excludes cache hits.'}
    if state.get('host_interruption_timing'):
        public['request_timing']['missing_supervised_timing_sequences']=[e['sequence'] for e in public['events'] if 'elapsed_seconds' not in e]
        public['request_timing']['missing_timing_note']='Known request timing sum excludes missing supervisor duration after transport loss; never interpreted as zero latency.'
    if public.get('non_dispatched_reservations'):
        public['request_timing'].update(
            definition='Supervisor-to-worker-exit, including the explicitly never-dispatched administrative checkpoint; excludes cache hits.',
            non_dispatched_supervised_seconds=sum(e.get('elapsed_seconds',0) for e in public['events'] if e.get('request_dispatched') is False),
            provider_dispatch_supervised_seconds=sum(e.get('elapsed_seconds',0) for e in public['events'] if e.get('request_dispatched') is not False))
    stops=[json.loads(p.read_text()) for p in sorted(RUN.glob('stopped-*.json'))]
    if partial and not any(s.get('stopped_utc')==state['stopped_utc'] for s in stops):stops.append(state)
    workflows=[]
    for i,w in enumerate(state['workflows']):
        finish=w.get('finished_utc')
        if finish is None:
            stop=next((s for s in stops if i<len(s['workflows'])
                       and s['workflows'][i]['started_utc']==w['started_utc']),None)
            if stop:finish=stop['stopped_utc']
        workflows.append({**w,'measured_until_utc':finish,
                          'elapsed_seconds':seconds(w['started_utc'],finish) if finish else None})
    public['workflow_timing']=workflows
    public['active_index_workflow_seconds']=sum(w['elapsed_seconds'] for w in workflows if w['elapsed_seconds'] is not None)
    gaps=[]
    for stop in stops:
        resumed=next((e['started_utc'] for e in state['executions'] if e.get('resume')
                      and e['started_utc']>stop['stopped_utc']),None)
        gaps.append({'stopped_utc':stop['stopped_utc'],'reason':stop['stop_reason'],
                     'resumed_utc':resumed,'seconds':seconds(stop['stopped_utc'],resumed) if resumed else None})
    public['diagnosed_stop_gaps']=gaps
    public['diagnosed_stop_gap_seconds']=sum(g['seconds'] for g in gaps if g['seconds'] is not None)
    public['index_elapsed_calendar_seconds']=(seconds(state['started_utc'],state['index_finished_utc'])
                                             if 'index_finished_utc' in state else None)
    public['preparation_timing']='Earlier research, dependency installation, adapter development, review and approval were not precisely timed; excluded from active indexing. The diagnosed stop gap is separately recorded.'
    public['evaluation_complete']=state['status']=='generation_complete'
    if partial:
        public['evidence_boundary']='Interrupted index only. No retrieval or feature result; timeout is not evidence of retrieval quality.'
        write('execution-interrupted.json',public)
        print(json.dumps({'exported':'interrupted_execution_only','generation_attempts':state['index_generation_attempts'],
                          'stop_reason':state['stop_reason'],'new_provider_calls':0}))
        return
    write('execution.json',public)
    write('extraction-format-diagnostics.json',output_diagnostics)
    write('environment.json',json.loads((RUN/'environment.json').read_text()))
    write('effective-config.json',json.loads((RUN/'effective-config.json').read_text()))
    write('preflight.json',json.loads((RUN/'preflight.json').read_text()))
    # Let readers resolve graph text-unit IDs even before query evaluation.
    # This is the exact frozen mapping, not a newly inferred source position.
    provenance=(ROOT/'.cache/pilot/provenance.json').read_bytes()
    assert hashlib.sha256(provenance).hexdigest()==json.loads((HERE/'size.json').read_text())['provenance_sha256']
    (OUT/'index').mkdir(exist_ok=True)
    (OUT/'index/text-unit-provenance.json').write_bytes(provenance)
    tables={}
    for name in ['entities','relationships','communities','community_reports']:
        path=RUN/'output'/f'{name}.parquet'
        df=pd.read_parquet(path)
        rows=json.loads(df.to_json(orient='records'))
        write(f'index/{name}.json',rows)
        tables[name]={'rows':len(df),'parquet_bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    entities=pd.read_parquet(RUN/'output/entities.parquet')
    covered={str(x) for row in entities['text_unit_ids'] for x in row}
    tables['text_units']={'rows':114,'text_units_referenced_by_entities':len(covered)}
    public_index_files=[p for p in (RUN/'output').rglob('*') if p.is_file()]
    write('index-summary.json',{'tables':tables,'entity_type_counts':entities['type'].value_counts().to_dict(),
        'all_output_file_bytes':sum(p.stat().st_size for p in public_index_files),
        'vector_store_bytes':sum(p.stat().st_size for p in (RUN/'output/lancedb').rglob('*') if p.is_file()),
        'original_cache_and_vectors_published':False})
    print(json.dumps({'exported':True,'operation_counts':public['operation_counts'],'embedding_estimate_usd':public['known_embedding_input_estimate_usd']}))


if __name__=='__main__':main()
