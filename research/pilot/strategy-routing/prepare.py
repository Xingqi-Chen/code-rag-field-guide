"""Offline preflight for a single text-routed GraphRAG strategy comparison.

Reads the completed graph and existing vectors. No model adapter or credential
is instantiated; a Python audit hook denies network access.
"""
import asyncio
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent
ROOT = PILOT.parents[1]
sys.path.insert(0,str(PILOT))
from routing_rules import route, RULES, SEED, call_bounds
import probe_runtime as probe
import code_prompt_experiment as variant

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'

def deny_network(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'}:
        raise RuntimeError('Strategy preflight forbids networking')
sys.addaudithook(deny_network)


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


async def main():
    assert not (HERE/'preflight.json').exists(), 'Preserve the first prepared observation'
    import pandas as pd
    from graphrag.query.indexer_adapters import (read_indexer_reports, read_indexer_communities,
        read_indexer_entities, read_indexer_report_embeddings)
    from graphrag.query.structured_search.global_search.community_context import GlobalCommunityContext
    from graphrag.tokenizer.get_tokenizer import get_tokenizer
    from graphrag.utils.api import get_embedding_store
    from graphrag.config.models.drift_search_config import DRIFTSearchConfig
    from graphrag.prompts.query.global_search_map_system_prompt import MAP_SYSTEM_PROMPT
    from graphrag.prompts.query.drift_search_system_prompt import DRIFT_PRIMER_PROMPT
    import graphrag.query.structured_search.drift_search.search as drift_search
    import graphrag.query.structured_search.drift_search.primer as drift_primer
    import graphrag.query.structured_search.drift_search.action as drift_action
    import graphrag.query.structured_search.drift_search.drift_context as drift_context
    import graphrag.query.structured_search.drift_search.state as drift_state
    assert importlib.metadata.version('graphrag')=='3.3.0'
    official=probe.MS/'packages/graphrag/graphrag'
    modules={'query/structured_search/drift_search/'+name+'.py':module for name,module in
        [('search',drift_search),('primer',drift_primer),('action',drift_action),('drift_context',drift_context),('state',drift_state)]}
    assert all(sha(Path(m.__file__))==sha(official/p) for p,m in modules.items())
    probe.tokenizers();variant.configure();config=variant.make_config()
    run=variant.RUN
    paid=read(run/'summary.json');published=read(variant.OUT/'execution.json')
    assert paid['status']==published['status']=='index_complete'
    for key in ['index_generation_attempts','generation_input_tokens','embedding_reserved_tokens','embedding_attempts','limits']:
        assert paid[key]==published[key]
    before=sha(run/'summary.json')
    original_unit_hash=sha(run/'output/text_units.parquet')
    index=read(variant.OUT/'index-summary.json')
    frames={}
    for name in ['entities','relationships','communities','community_reports','text_units']:
        path=run/'output'/f'{name}.parquet'
        if 'sha256' in index['tables'][name]:assert sha(path)==index['tables'][name]['sha256']
        else:assert name=='text_units'
        frames[name]=pd.read_parquet(path)
    tokenizer=get_tokenizer(encoding_model='o200k_base')
    store=get_embedding_store(config.vector_store,'community_full_content')
    reports=read_indexer_reports(frames['community_reports'],frames['communities'],2)
    read_indexer_report_embeddings(reports,store)
    assert len(reports)==367 and all(r.full_content_embedding is not None and len(r.full_content_embedding)==3072 for r in reports)
    root_reports=read_indexer_reports(frames['community_reports'],frames['communities'],0)
    builder=GlobalCommunityContext(root_reports,
        read_indexer_communities(frames['communities'],frames['community_reports']),
        read_indexer_entities(frames['entities'],frames['communities'],0),
        tokenizer=tokenizer,random_state=SEED,dynamic_community_selection=False)
    global_context=await builder.build_context('offline preflight',use_community_summary=False,
        max_context_tokens=12000,shuffle_data=True,include_community_rank=True)
    assert len(root_reports)==23 and len(global_context.context_chunks)==4
    write(HERE/'global-map-contexts.json',{'community_level':0,'reports':23,
        'chunks':global_context.context_chunks,
        'records':{k:json.loads(v.to_json(orient='records')) for k,v in global_context.context_records.items()}})
    main=read(PILOT/'questions.json');supplement=read(PILOT/'global-questions.json')
    by_id={q['id']:q for q in main}
    for q in supplement:
        if q['id'] in by_id:assert q['query']==by_id[q['id']]['query']
        else:by_id[q['id']]=q
    queries=[{'id':qid,'query':q['query'],'original_split':q.get('split'),
        'cohorts':(['main20'] if qid in {x['id'] for x in main} else [])+
                  (['supplement6'] if qid in {x['id'] for x in supplement} else []),
        'route':route(q['query'])} for qid,q in by_id.items()]
    counts=Counter(q['route']['method'] for q in queries)
    assert dict(counts)=={'local':8,'drift':13,'global':2}
    write(HERE/'queries.json',queries)
    max_map_input=max(len(tokenizer.encode(MAP_SYSTEM_PROMPT.format(context_data=c,max_length=1000)))+
        len(tokenizer.encode(q['query']))+512 for c in global_context.context_chunks for q in queries)
    assert max_map_input<=16000
    longest=sorted(reports,key=lambda r:len(tokenizer.encode(r.full_content)),reverse=True)[:2]
    max_primer_input=max(len(tokenizer.encode(DRIFT_PRIMER_PROMPT.format(query=q['query'],
        community_reports='\n\n'.join(r.full_content for r in longest)))) for q in queries)+512
    bounds=call_bounds(counts,3,len(queries),len(global_context.context_chunks))
    carry={'generation_reservations':paid['index_generation_attempts'],
        'generation_common_input_tokens':paid['generation_input_tokens'],
        'embedding_tokens':paid['embedding_reserved_tokens'],'embedding_attempts':paid['embedding_attempts']}
    new_embed_items=counts['drift']*(1+2*2)+3
    new_embed_tokens_max=new_embed_items*8000*3
    budget={**bounds,'carry':carry,'generation_limit_current':1600,
        'generation_reservations_remaining':1600-carry['generation_reservations'],
        'generation_limit_required_for_full_retry_bound':carry['generation_reservations']+bounds['generation_with_two_extra_transient_attempts_per_request_max'],
        'generation_limit_increase_required':carry['generation_reservations']+bounds['generation_with_two_extra_transient_attempts_per_request_max']-1600,
        'per_question_method_common_input_cap_including_retries':64000,
        'unique_questions':len(queries),'answer_methods':4,
        'new_common_input_hard_max':len(queries)*4*64000,
        'cumulative_common_input_hard_max':carry['generation_common_input_tokens']+len(queries)*4*64000,
        'generation_common_input_limit_unchanged':8000000,
        'embedding_new_items_max_no_retry':new_embed_items,
        'embedding_attempts_max_with_retries':new_embed_items*3,
        'embedding_tokens_max_with_retries':new_embed_tokens_max,
        'embedding_cumulative_usd_hard_max':str(Decimal(carry['embedding_tokens']+new_embed_tokens_max)*Decimal('.13')/1000000),
        'embedding_cumulative_usd_limit_unchanged':'1.00',
        'note':'Worst transient bound assumes two extra attempts for every logical generation/embedding request. Common-input64k is a hard cumulative per-question-method cap; repeated transient failures may exhaust it before all stages finish. Such failures remain in denominators. Provider-reported input may differ; requested output2048 is known not to be enforced by this proxy, so no total-generation-dollar guarantee.'}
    assert budget['cumulative_common_input_hard_max']<=8000000
    assert Decimal(budget['embedding_cumulative_usd_hard_max'])<=1
    assert budget['embedding_attempts_max_with_retries']+carry['embedding_attempts']<=1000
    paths=[PILOT/'questions.json',PILOT/'gold.json',PILOT/'global-questions.json',PILOT/'global-gold.json',
        variant.OUT/'execution.json',variant.OUT/'index-summary.json',HERE/'routing_rules.py',HERE/'queries.json',HERE/'global-map-contexts.json']
    result={'prepared_utc':datetime.now(timezone.utc).isoformat(),'status':'offline_prepared_budget_confirmation_required',
        'external_calls':0,'credentials_read':False,'index_rebuilt':False,'gold_read_by_prepare':False,
        'source_commit':__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'paid_ledger_sha256_unchanged':before,'text_units_parquet_sha256':original_unit_hash,'route_counts_unique':dict(counts),'budget':budget,
        'official_version':'3.3.0','official_commit':'5faaaf4f5685fa2056fa8c3bf9342cb089f2942f',
        'official_source_sha256':{p:sha(official/p) for p in modules},
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in paths},
        'drift_level2_reports_with_existing_embeddings':len(reports),'global_level0_reports':len(root_reports),
        'global_map_batches':len(global_context.context_chunks),
        'global_map_context_tokens':[len(tokenizer.encode(c)) for c in global_context.context_chunks],
        'max_map_input_including_512_common_instruction_allowance':max_map_input,
        'max_two_report_primer_input_including_512_allowance':max_primer_input,
        'official_default_drift_config':DRIFTSearchConfig().model_dump(),
        'config_overrides':{'drift_k_followups':2,'n_depth':2,'primer_folds':1,'concurrency':1,
            'local_search_max_data_tokens':4000,'local_search_text_unit_prop':.5,'local_search_community_prop':.15},
        'random_template_rule':'Replace only primer.secrets reference with a deterministic choice selecting minimum sha256(seed:raw_query:report_id). Save report ID and hash. No gold or result access.',
        'random_followup_rule':'Use a dedicated random.Random seeded from seed and raw question per search for state.random.shuffle; preserve upstream shuffle behavior. PYTHONHASHSEED fixed before process startup.',
        'request_times_seconds':{'generation':120,'embedding':30},'total_wall_deadline':None}
    assert before==sha(run/'summary.json')
    write(HERE/'preflight.json',result)
    print(json.dumps({'status':result['status'],'routes':dict(counts),'budget':budget},indent=2))

if __name__=='__main__':asyncio.run(main())
