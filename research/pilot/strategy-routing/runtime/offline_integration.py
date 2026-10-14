"""Real pinned query engines + existing graph, synthetic transport, no network.

The result is software compatibility evidence, never retrieval/answer quality.
"""
import asyncio
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
FORBIDDEN=[]
def deny(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'}:
        FORBIDDEN.append(event);raise RuntimeError('offline integration forbids networking')
    if event=='open' and isinstance(args[0],(str,bytes)) and 'credentials.env' in str(args[0]):
        FORBIDDEN.append('credential_read');raise RuntimeError('offline integration forbids credentials')
sys.addaudithook(deny)
from bounded import Runtime,Halt,MODEL,EMBED,read,file_sha
from runner import Data,execute_cell,verify_protocol
from official import Completion

class Synthetic:
    def __init__(self,invalid_local=False):self.calls=[];self.invalid_local=invalid_local
    def dispatch(self,request,response,seconds):
        body=read(request);state=read(request.parent/'summary.json');stage=state['events'][-1]['stage'];self.calls.append(stage)
        if body['service']=='embedding':
            value={'model':EMBED,'data':[{'index':0,'embedding':[1.0]*3072}],'usage':{'prompt_tokens':10,'total_tokens':10}}
        else:
            if stage=='primer':text=json.dumps({'intermediate_answer':'Synthetic initial answer.','score':50,'follow_up_queries':[f'check source branch {i}' for i in range(5)]})
            elif stage=='local':text='{"response": null}' if self.invalid_local else json.dumps({'response':'Synthetic local answer [Data: Sources (1)].','score':50,'follow_up_queries':[]})
            elif stage=='map':text=json.dumps({'points':[{'description':'Synthetic map point [Data: Reports (1)].','score':50}]})
            elif stage=='hyde':text='Synthetic hypothetical answer for query expansion.'
            else:text='Synthetic final answer. This is not an experiment result.'
            value={'model':MODEL,'choices':[{'finish_reason':'stop','message':{'content':text}}],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}
        return {'http_status':200,'response':value}

async def main():
    queries=verify_protocol();pre=read(HERE.parent/'preflight.json')
    old=ROOT/'.cache/pilot/code-prompt-20261013/summary.json';before=file_sha(old)
    data=Data();checks=[]
    from offline_worker import check_worker
    worker_checks=check_worker();checks.append('real worker with fake HTTP opener, exact schema and embedding payload, duplicate dispatch rejected')
    # All cached main contexts resolve without embedding or generation.
    with tempfile.TemporaryDirectory() as tmp:
        fake=Synthetic();runtime=Runtime(Path(tmp)/'run',fake,data.enc,data.eenc,create=True,synthetic=True,wait=lambda _:None)
        for q in queries:
            if 'main20' not in q['cohorts']:continue
            for method in ('local','bm25','ms_basic','hybrid'):
                cell=runtime.cell(q['id'],method,method);context=data.standard_context(q,method,cell)
                assert context['context_tokens']<=12000
        assert fake.calls==[];runtime.close();checks.append('80 original12k contexts resolve without API')
    observations=[]
    with tempfile.TemporaryDirectory() as tmp:
        fake=Synthetic();runtime=Runtime(Path(tmp)/'run',fake,data.enc,data.eenc,create=True,synthetic=True,wait=lambda _:None)
        q=next(q for q in queries if q['route']['method']=='drift')
        c=runtime.cell(q['id'],'routed_graphrag','drift');result=await execute_cell(data,c,q)
        assert result['status']=='complete',result.get('failure')
        events=[e for e in runtime.state['events'] if e['cell']==c.key]
        assert Counter(e['stage'] for e in events if e['service']=='generation')=={'hyde':1,'primer':1,'local':4,'reduce':1}
        assert sum(e['service']=='embedding' for e in events)<=5
        assert len(c.data['evidence'])==4 and c.data['outer_timer_includes_reduce']
        assert all(any(m['content'][0]['text'].startswith('Answer in English using only') for m in req['body']['input']) for req in runtime.state['requests'].values() if req['service']=='generation')
        observations.append({'route':'drift','generation':7,'physical_embedding':sum(e['service']=='embedding' for e in events),'source_context_stages':len(c.data['evidence'])})
        selection=[x for x in c.data['decisions'] if x['kind'] in {'hyde_template','pending_action_order'}]
        # New question must prime despite prior cell's nonempty QueryState.
        q2=next(x for x in queries if x['route']['method']=='drift' and x['id']!=q['id'])
        c2=runtime.cell(q2['id'],'routed_graphrag','drift');await execute_cell(data,c2,q2)
        assert c2.data['status']=='complete' and any(x['kind']=='hyde_template' for x in c2.data['decisions'])
        assert len([x for x in c2.data['uses'] if x['stage']=='primer'])==1
        # Re-executing a deterministic whole query after a postprocessing-only
        # interruption consumes cached replies, not new physical attempts.
        count=len(runtime.state['events']);c.data['status']='running';await execute_cell(data,c,q)
        assert len(runtime.state['events'])==count
        repeated=[x for x in c.data['decisions'] if x['kind'] in {'hyde_template','pending_action_order'}]
        assert repeated[:len(selection)]==repeated[len(selection):]
        checks+=['real DRIFT7-stage official interface','per-query fresh state','deterministic replay uses cache','all subcalls receive evidence-only restriction']
        qg=next(x for x in queries if x['route']['method']=='global');g=runtime.cell(qg['id'],'routed_graphrag','global')
        await execute_cell(data,g,qg);assert g.data['status']=='complete',g.data.get('failure')
        ges=[e for e in runtime.state['events'] if e['cell']==g.key]
        assert Counter(e['stage'] for e in ges)=={'map':4,'reduce':1}
        observations.append({'route':'global','generation':5,'physical_embedding':0});checks.append('actual frozen four-map Global plus reduce')
        # New supplemental question exercises actual BM25, Basic vector and hybrid retrieval.
        qe=next(x for x in queries if x['id']=='F02-plan')
        for method in ('bm25','ms_basic','hybrid'):
            cell=runtime.cell(qe['id'],method,method);await execute_cell(data,cell,qe)
            assert cell.data['status']=='complete',cell.data.get('failure')
        checks.append('three extra-question baselines with shared exact query embedding')
        runtime.close()
    with tempfile.TemporaryDirectory() as tmp:
        fake=Synthetic(invalid_local=True);runtime=Runtime(Path(tmp)/'run',fake,data.enc,data.eenc,create=True,synthetic=True,wait=lambda _:None)
        c=runtime.cell(q['id'],'routed_graphrag','drift');await execute_cell(data,c,q)
        assert c.data['status']=='failed' and c.data['failure']=='local_action_schema'
        assert fake.calls.count('local')==1 and 'reduce' not in fake.calls
        runtime.close();checks.append('invalid Local JSON escapes upstream handlers and stops subcalls')
    assert before==file_sha(old)==pre['paid_ledger_sha256_unchanged']
    assert not FORBIDDEN
    print(json.dumps({'status':'offline_integration_passed','new_model_api_calls':0,'new_embedding_api_calls':0,'credentials_read':False,
        'old_paid_ledger_unchanged':True,'worker_checks':worker_checks,'synthetic_observations':observations,'checks':checks,
        'limitations':['Synthetic generations and dynamic embeddings are not answer-quality or retrieval-effectiveness evidence.','Existing source graph and exact official query engines are real.','No actual service transport compatibility is asserted before authorized execution.']},indent=2))

if __name__=='__main__':asyncio_complete=asyncio.run(main())
