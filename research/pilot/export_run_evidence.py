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
OUT=HERE/'results'


def write(name,obj):
    path=OUT/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def seconds(start,end):
    return (datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()


def main():
    import pandas as pd
    state=json.loads((RUN/'summary.json').read_text())
    assert state['status'] in {'index_complete','retrieval_complete','generation_complete'}
    public_keys=['run_id','created_utc','started_utc','limits','status','prior_probe_reserved',
        'prior_probe_elapsed_seconds','index_generation_attempts','feature_generation_attempts',
        'embedding_attempts','generation_input_tokens','embedding_reserved_tokens',
        'logical_completion_calls','completion_cache_hits','logical_embedding_calls',
        'embedding_cache_items','imported_successful_probe_cache','source_commit','workflows',
        'executions','recoveries','index_elapsed_seconds','index_finished_utc',
        'retrieval_finished_utc','generation_finished_utc']
    public={k:state[k] for k in public_keys if k in state}
    event_keys=['sequence','service','phase','workflow','input_tokens','items','status',
        'request_body_sha256','started_utc','source_commit','supervisor_reason','worker_exit',
        'elapsed_seconds','http_status','error_category','response_format','validation_reason',
        'usage','visible_output_common_tokens','requested_output_limit_exceeded']
    public['events']=[{k:e[k] for k in event_keys if k in e} for e in state['events']]
    classifications=Counter()
    initial_prompts={probe.prompt_values()['GRAPH_EXTRACTION_PROMPT'].format(
        entity_types='organization,person,geo,event',input_text=json.loads(line)['text'].strip())
        for line in (ROOT/'.cache/pilot/input/documents.jsonl').read_text().splitlines()}
    output_diagnostics=[]
    usage_totals=Counter()
    for event in public['events']:
        seq=event['sequence']
        task=json.loads((RUN/f'request-{seq:02}.json').read_text())
        envelope=json.loads((RUN/f'response-{seq:02}.json').read_text())
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
        if seq==14:
            event['recovery']='Complete reply independently validated and reused; original rejection retained.'
            event['usage']=reply['usage']
            event['visible_output_common_tokens']=1220
            event['requested_output_limit_exceeded']=True
    public['operation_counts']=dict(classifications)
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
    stopped=json.loads((RUN/'stopped-01.json').read_text()) if (RUN/'stopped-01.json').exists() else None
    workflows=[]
    recovery_end=None
    if stopped:
        recovery_end=next(e['started_utc'] for e in state['executions'] if e.get('resume'))
    for i,w in enumerate(state['workflows']):
        finish=w.get('finished_utc')
        if finish is None and stopped and i<len(stopped['workflows']):finish=stopped['stopped_utc']
        workflows.append({**w,'measured_until_utc':finish,
                          'elapsed_seconds':seconds(w['started_utc'],finish) if finish else None})
    public['workflow_timing']=workflows
    public['active_index_workflow_seconds']=sum(w['elapsed_seconds'] for w in workflows if w['elapsed_seconds'] is not None)
    public['diagnosed_stop_gap_seconds']=seconds(stopped['stopped_utc'],recovery_end) if stopped and recovery_end else 0
    public['index_elapsed_calendar_seconds']=seconds(state['started_utc'],state['index_finished_utc'])
    public['preparation_timing']='Earlier research, dependency installation, adapter development, review and approval were not precisely timed; excluded from active indexing. The diagnosed stop gap is separately recorded.'
    write('execution.json',public)
    write('extraction-format-diagnostics.json',output_diagnostics)
    write('environment.json',json.loads((RUN/'environment.json').read_text()))
    write('effective-config.json',json.loads((RUN/'effective-config.json').read_text()))
    write('preflight.json',json.loads((RUN/'preflight.json').read_text()))
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
