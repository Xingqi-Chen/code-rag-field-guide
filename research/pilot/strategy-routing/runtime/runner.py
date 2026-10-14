"""Fixed 23-query/four-method controller. No gold is read during execution."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import time
from types import SimpleNamespace as NS

HERE=Path(__file__).resolve().parent
PROTOCOL=HERE.parent
PILOT=HERE.parents[1]
ROOT=PILOT.parents[1]
sys.path.insert(0,str(PILOT));sys.path.insert(0,str(PROTOCOL))
os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
from bounded import Runtime,Halt,read,save,file_sha,MODEL,DENIED
from official import Completion,Embedding,drift
from routing_rules import route
RUN=ROOT/'.cache/pilot/strategy-routing-20261014'
BASE_PROMPT=('You are answering a code-maintenance question about Requests 2.32.3. '
             'Use the supplied context below, cite its Sources IDs and named locations. '
             'Do not use external knowledge or tools.\n\n{context}')


def verify_protocol():
    if os.environ.get('PYTHONHASHSEED')!='20261012':raise Halt('fixed_process_hash_seed_required')
    for name,sha in read(PROTOCOL/'freeze.json')['sha256'].items():
        if file_sha(ROOT/name)!=sha:raise Halt('frozen_protocol_changed')
    for name,sha in read(PROTOCOL/'preflight.json')['source_sha256'].items():
        if file_sha(ROOT/name)!=sha:raise Halt('source_snapshot_changed')
    return read(PROTOCOL/'queries.json')

class Data:
    """Read-only old graph and vectors; never constructs an indexing pipeline."""
    def __init__(self):
        import probe_runtime as probe
        import full_index
        import pandas as pd
        from graphrag.query.indexer_adapters import (read_indexer_text_units,read_indexer_entities,read_indexer_reports,read_indexer_relationships,read_indexer_report_embeddings)
        from graphrag.utils.api import get_embedding_store
        from graphrag.tokenizer.get_tokenizer import get_tokenizer
        # Querying needs only vector-store settings. The indexing variant's
        # configure() also replaces the process supervisor, so never invoke it
        # while opening an existing graph for this independent controller.
        probe.tokenizers();config=full_index.make_config()
        self.index=ROOT/'.cache/pilot/code-prompt-20261013'
        config.vector_store.db_uri=str(self.index/'output/lancedb')
        self.probe=probe;self.enc,self.eenc=probe.tokenizers();self.tok=get_tokenizer(encoding_model='o200k_base')
        self.count=lambda s:len(self.tok.encode(s))
        df={name:pd.read_parquet(self.index/'output'/f'{name}.parquet') for name in ('entities','communities','community_reports','relationships','text_units')}
        old=read(PILOT/'results/code-prompt/index-summary.json')
        for name in ('entities','communities','community_reports','relationships'):
            if file_sha(self.index/'output'/f'{name}.parquet')!=old['tables'][name]['sha256']:raise Halt('graph_table_changed')
        if file_sha(self.index/'output/text_units.parquet')!=read(PROTOCOL/'preflight.json')['text_units_parquet_sha256']:raise Halt('text_units_changed')
        self.units=read_indexer_text_units(df['text_units']);provs={p['ms_text_unit_id']:p for p in read(PILOT/'results/index/text-unit-provenance.json')}
        self.sources={str(u.short_id):{'id':u.id,'text':u.text,'provenance':provs[u.id]} for u in self.units}
        for source in self.sources.values():
            if hashlib.sha256(source['text'].encode()).hexdigest()!=source['provenance']['text_sha256']:raise Halt('source_text_changed')
        self.entities=read_indexer_entities(df['entities'],df['communities'],2)
        self.reports=read_indexer_reports(df['community_reports'],df['communities'],2)
        self.relations=read_indexer_relationships(df['relationships'])
        self.entity_store=get_embedding_store(config.vector_store,'entity_description')
        self.text_store=get_embedding_store(config.vector_store,'text_unit_text')
        read_indexer_report_embeddings(self.reports,get_embedding_store(config.vector_store,'community_full_content'))
        by_id={u.id:u for u in self.units}
        self.ordered=[by_id[p['ms_text_unit_id']] for p in read(PILOT/'results/provenance.json')]
        self.vectors=[self.text_store.search_by_id(u.id).vector for u in self.ordered]
        if hashlib.sha256(probe.canonical(self.vectors).encode()).hexdigest()!=read(PILOT/'results/retrieval.json')['shared_vector_sha256']:raise Halt('source_vectors_changed')
        if len(self.reports)!=367 or any(len(r.full_content_embedding)!=3072 for r in self.reports):raise Halt('missing_report_vector')
        self.global_context=read(PROTOCOL/'global-map-contexts.json')
        self.imported={x['cache_key']:x['cache_sha256'] for x in read(self.index/'imported-embedding-cache.json')}
    def embedder(self,cell):
        data=self
        class Cached(Embedding):
            def embedding(self,*,input):
                values=[]
                for text in input:
                    key=data.probe.digest(data.probe.canonical([data.probe.EMBED,3072,text]).encode())
                    cached=data.index/'embedding-cache'/f'{key}.json'
                    if key in data.imported:
                        if file_sha(cached)!=data.imported[key]:cell.fail('old_embedding_cache_changed')
                        vector=read(cached)['vector']
                        cell.record('decisions',{'kind':'old_query_embedding_reused','cache_key':key,'sha256':file_sha(cached)})
                    else:vector=cell.embed([text])[0]
                    values.append(vector)
                return NS(first_embedding=values[0],data=[NS(embedding=v,index=i) for i,v in enumerate(values)])
        return Cached(cell)
    def standard_context(self,q,method,cell):
        from full_retrieve import adapt,budget_tables,render,source_mapping
        if q['id'].startswith('Q'):
            folder='code-prompt/' if method=='local' else ''
            label='ms_local_code_prompt' if method=='local' else method
            path=PILOT/'results'/folder/'contexts'/f'{q["id"]}-{label}-12000.json'
            result=read(path)
            if result['query']!=q['query']:cell.fail('reused_query_changed')
            return {'context':result['final_context'],'sources':result['sources'],'source_text_tokens':result['source_text_tokens'],
                'context_tokens':result['final_context_tokens'],'reused_context_file':str(path.relative_to(ROOT)),'reused_sha256':file_sha(path)}
        if method=='local':cell.fail('unexpected_extra_local_route')
        import baselines
        from graphrag.query.structured_search.basic_search.basic_context import BasicSearchContext
        texts=[u.text for u in self.ordered];embedder=self.embedder(cell)
        if method in {'bm25','hybrid'}:
            ranking=baselines.bm25(texts,q['query']) if method=='bm25' else baselines.hybrid(texts,q['query'],self.vectors,embedder.embedding(input=[q['query']]).first_embedding)
            records={'sources':[{'id':str(self.ordered[i].short_id),'text':texts[i]} for i in ranking]}
        else:
            basic=BasicSearchContext(text_embedder=embedder,text_unit_embeddings=self.text_store,text_units=self.units,tokenizer=self.tok)
            r=basic.build_context(q['query'],k=10,max_context_tokens=12000)
            records={k:json.loads(v.to_json(orient='records')) for k,v in r.context_records.items()}
        tables=budget_tables(adapt(records,self.sources),12000,self.count);context=render(tables);mapping=source_mapping(tables,self.sources)
        return {'context':context,'sources':mapping,'source_text_tokens':sum(self.count(self.sources[x['short_id']]['text']) for x in mapping),'context_tokens':self.count(context)}
    def drift_builder(self,cell):
        from graphrag.config.models.drift_search_config import DRIFTSearchConfig
        from graphrag.query.structured_search.drift_search.drift_context import DRIFTSearchContextBuilder
        from graphrag.query.structured_search.local_search.mixed_context import LocalSearchMixedContext
        from full_retrieve import source_mapping,adapt,budget_tables,render
        from graphrag.query.context_builder.builders import ContextBuilderResult
        import pandas as pd
        embedding=self.embedder(cell);data=self
        local=LocalSearchMixedContext(entities=self.entities,entity_text_embeddings=self.entity_store,text_embedder=embedding,text_units=self.units,
            community_reports=self.reports,relationships=self.relations,covariates={},tokenizer=self.tok)
        class RecordedLocal:
            def build_context(self,query,**kwargs):
                r=local.build_context(query,**kwargs)
                records={k:json.loads(v.to_json(orient='records')) for k,v in r.context_records.items()}
                tables=budget_tables(adapt(records,data.sources),4000,data.count)
                mapping=source_mapping(tables,data.sources);context=render(tables)
                cell.record('evidence',{'stage':'local','query':query,'context':context,'upstream_context':r.context_chunks,'records':records,'sources':mapping,
                    'source_text_tokens':sum(data.count(data.sources[x['short_id']]['text']) for x in mapping),'context_tokens':data.count(context)})
                return ContextBuilderResult(context_chunks=context,context_records={t['name']:pd.DataFrame(t['rows']) for t in tables if t['rows']})
        cfg=DRIFTSearchConfig(**read(PROTOCOL/'preflight.json')['config_overrides'])
        return DRIFTSearchContextBuilder(model=Completion(cell,self.tok),config=cfg,text_embedder=embedding,entities=self.entities,
            entity_text_embeddings=self.entity_store,reports=self.reports,local_mixed_context=RecordedLocal(),tokenizer=self.tok,response_type='multiple paragraphs')
    def global_builder(self,cell):
        from graphrag.query.context_builder.builders import ContextBuilderResult
        import pandas as pd
        data=self
        class FixedGlobal:
            async def build_context(self,query,**kwargs):
                cell.record('evidence',{'stage':'map','sources':[],'source_text_tokens':0,'context_tokens':sum(data.count(x) for x in data.global_context['chunks']),
                    'context':data.global_context['chunks'],'frozen_file':'research/pilot/strategy-routing/global-map-contexts.json'})
                return ContextBuilderResult(context_chunks=data.global_context['chunks'],context_records={k:pd.DataFrame(v) for k,v in data.global_context['records'].items()})
        return FixedGlobal()

async def execute_cell(data,cell,q):
    route_name=cell.data['route'];start=time.monotonic();initial_events=len(cell.runtime.state['events'])
    from bounded import now
    segment={'started_utc':now(),'initial_event_count':initial_events}
    cell.data.setdefault('execution_segments',[]).append(segment);cell.runtime.persist()
    try:
        if route_name=='drift':result=await drift(cell,q['query'],data.drift_builder(cell),data.tok);answer=result.response
        elif route_name=='global':
            from graphrag.query.structured_search.global_search.search import GlobalSearch
            engine=GlobalSearch(model=Completion(cell,data.tok),context_builder=data.global_builder(cell),tokenizer=data.tok,
                max_data_tokens=12000,map_max_length=1000,reduce_max_length=2000,allow_general_knowledge=False,json_mode=False,concurrent_coroutines=1)
            result=await engine.search(q['query']);answer=result.response
        else:
            context=data.standard_context(q,route_name,cell);cell.record('evidence',{'stage':'answer',**context})
            answer,_,_=cell.generate([{'role':'system','content':BASE_PROMPT.format(context=context['context'])},{'role':'user','content':q['query']}])
        if not isinstance(answer,str) or not answer.strip():cell.fail('no_final_answer')
        cell.data.update(status='complete',answer=answer)
    except Halt as error:
        cell.data.update(status='failed',failure=str(error),answer=None)
        if error.fatal or str(error) in DENIED:raise
    except Exception:
        cell.data.update(status='failed',failure='query_engine_exception_redacted',answer=None)
    finally:
        segment.update(elapsed_seconds=time.monotonic()-start,finished_utc=now(),
            event_sequences=list(range(initial_events+1,len(cell.runtime.state['events'])+1)))
        cell.data.update(elapsed_seconds=sum(s.get('elapsed_seconds',0) for s in cell.data['execution_segments']),finished_utc=now(),
            interrupted_segments_with_unknown_duration=sum('elapsed_seconds' not in s for s in cell.data['execution_segments']),
            outer_timer_includes_reduce=True,new_event_sequences=list(range(initial_events+1,len(cell.runtime.state['events'])+1)))
        cell.runtime.persist()
    return cell.data

async def execute():
    from transport import Transport,check_authorization
    check_authorization();queries=verify_protocol();data=Data()
    runtime=Runtime(RUN,Transport(),data.enc,data.eenc,create=not RUN.exists())
    runtime.state.setdefault('execution_sessions',[]).append({
        'started_utc':__import__('bounded').now(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'implementation_sha256':read(HERE/'live-readiness.json')['implementation_sha256'],
        'python_version':sys.version.split()[0],'process_hash_seed':os.environ['PYTHONHASHSEED'],
        'prior_counts_preserved':runtime.state['counts'].copy()})
    runtime.persist()
    try:
        for q in queries:
            if route(q['query'])!=q['route']:raise Halt('route_changed')
            for method in ('routed_graphrag','bm25','ms_basic','hybrid'):
                route_name=q['route']['method'] if method=='routed_graphrag' else method
                cell=runtime.cell(q['id'],method,route_name)
                if cell.data['status'] in {'complete','failed'}:continue
                await execute_cell(data,cell,q)
                print(json.dumps({'event':'cell_finished','question':q['id'],'method':method,'route':route_name,'status':cell.data['status'],
                    'failure':cell.data.get('failure'),'cumulative_counts':runtime.state['counts']},ensure_ascii=False),flush=True)
        runtime.state.update(status='complete_with_recorded_failures' if any(c['status']=='failed' for c in runtime.state['cells'].values()) else 'complete')
        runtime.persist()
    finally:runtime.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['execute']);parser.parse_args()
    asyncio.run(execute())
