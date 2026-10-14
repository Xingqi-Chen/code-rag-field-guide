"""Audited adapters for pinned official GraphRAG queries, not graph algorithms."""
from contextlib import contextmanager
import hashlib
import json
import random
import threading
from types import SimpleNamespace as NS
from bounded import Halt,MODEL,strict_json,digest

RANDOM_LOCK=threading.Lock()

class Completion:
    def __init__(self,cell,tokenizer):self.cell=cell;self.tokenizer=tokenizer
    async def completion_async(self,**kwargs):
        try:return await self._complete(**kwargs)
        except Halt:raise
        except Exception:self.cell.fail('completion_adapter_exception_redacted')
    async def _complete(self,**kwargs):
        allowed={'messages','response_format','response_format_json_object','stream','temperature','top_p','n','max_completion_tokens'}
        if set(kwargs)-allowed:self.cell.fail('unexpected_completion_arguments')
        for key,allowed_values in {'temperature':(None,0),'top_p':(None,1),'n':(None,1),'max_completion_tokens':(None,2048)}.items():
            if kwargs.get(key) not in allowed_values:self.cell.fail('nondefault_upstream_parameters')
        from graphrag.query.structured_search.drift_search.primer import PrimerResponse
        fmt=None;route=self.cell.data['route'];response_format=kwargs.get('response_format')
        if response_format is not None:
            if response_format is not PrimerResponse:self.cell.fail('unregistered_response_schema')
            schema=PrimerResponse.model_json_schema();schema['additionalProperties']=False
            fmt={'type':'json_schema','name':'PrimerResponse','strict':True,'schema':schema};stage='primer'
        elif kwargs.get('response_format_json_object'):
            fmt={'type':'json_object'};stage='local' if route=='drift' else 'map'
        elif route=='drift':stage='hyde' if isinstance(kwargs['messages'],str) else 'reduce'
        elif route=='global':stage='reduce'
        else:stage='answer'
        text,usage,key=self.cell.generate(kwargs['messages'],stage,fmt)
        formatted=None
        if stage in {'primer','local','map'}:
            try:
                value=strict_json(text)
                if stage=='primer':
                    if not isinstance(value,dict) or set(value)!={'intermediate_answer','score','follow_up_queries'}:raise Halt('primer_schema_fields')
                    formatted=PrimerResponse.model_validate(value,strict=True)
                    if not value['follow_up_queries']:raise Halt('primer_no_followups')
                elif stage=='local':
                    if not isinstance(value,dict) or set(value)!={'response','score','follow_up_queries'} or not isinstance(value['response'],str) or not value['response'].strip() or type(value['score']) not in (int,float) or not isinstance(value['follow_up_queries'],list) or any(not isinstance(s,str) or not s.strip() for s in value['follow_up_queries']):raise Halt('local_action_schema')
                else:
                    if not isinstance(value,dict) or set(value)!={'points'} or not isinstance(value['points'],list):raise Halt('global_map_schema')
                    if any(not isinstance(p,dict) or set(p)!={'description','score'} or not isinstance(p['description'],str) or type(p['score']) is not int for p in value['points']):raise Halt('global_map_point_schema')
                self.cell.record('decisions',{'kind':'structured_response','stage':stage,'request_key':key,'parsed':value,'repair_applied':False})
            except Halt as error:self.cell.fail(str(error))
            except Exception:self.cell.fail('structured_response_schema_invalid')
        self.cell.record('decisions',{'kind':'adapter_arguments','stage':stage,'request_key':key,
            'accepted_kwargs':sorted(kwargs),'provider_parameter_policy':'Fixed provider defaults: n1, top_p1, temperature not sent; output2048. JSON/schema and stream recorded explicitly.',
            'stream_requested_by_upstream':bool(kwargs.get('stream'))})
        if kwargs.get('stream'):
            async def chunks():yield NS(choices=[NS(delta=NS(content=text))])
            return chunks()
        return NS(content=text,formatted_response=formatted,model=MODEL,usage=usage,choices=[NS(message=NS(content=text))])

class Embedding:
    def __init__(self,cell):self.cell=cell
    def embedding(self,*,input):
        try:
            vectors=self.cell.embed(input)
            return NS(first_embedding=vectors[0],data=[NS(embedding=v,index=i) for i,v in enumerate(vectors)])
        except Halt:raise
        except Exception:self.cell.fail('embedding_adapter_exception_redacted')
    async def embedding_async(self,*,input):return self.embedding(input=input)

@contextmanager
def deterministic(query,cell):
    import graphrag.query.structured_search.drift_search.primer as primer
    import graphrag.query.structured_search.drift_search.state as state
    # Whole query is serial; only replace these module references, never mutate
    # the process-wide secrets/random modules. Restore them even on Halt.
    with RANDOM_LOCK:
        old_choice,old_random=primer.secrets,state.random
        def choice(reports):
            selected=min(reports,key=lambda r:hashlib.sha256(f'20261012:{query}:{r.id}'.encode()).hexdigest())
            cell.record('decisions',{'kind':'hyde_template','report_id':selected.id,'report_content_sha256':hashlib.sha256(selected.full_content.encode()).hexdigest()})
            return selected
        rng=random.Random(int(hashlib.sha256(f'20261012:{query}'.encode()).hexdigest(),16))
        def shuffle(actions):
            rng.shuffle(actions)
            cell.record('decisions',{'kind':'pending_action_order','queries':[a.query for a in actions]})
        primer.secrets=NS(choice=choice);state.random=NS(shuffle=shuffle)
        try:yield
        finally:primer.secrets=old_choice;state.random=old_random

async def drift(cell,query,builder,tokenizer):
    from graphrag.query.structured_search.drift_search.search import DRIFTSearch
    from graphrag.query.structured_search.drift_search.state import QueryState
    model=Completion(cell,tokenizer)
    builder.model=model
    engine=DRIFTSearch(model=model,context_builder=builder,tokenizer=tokenizer,query_state=QueryState())
    with deterministic(query,cell):return await engine.search(query,reduce=True)
