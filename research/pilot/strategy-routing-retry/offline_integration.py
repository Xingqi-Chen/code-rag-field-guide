"""Real six official DRIFT paths with inherited exact caches; fake new transport."""
import asyncio
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
FORBIDDEN=[]
def deny(event,args):
    if event in {'socket.connect','socket.getaddrinfo','http.client.connect','urllib.Request'} or event=='open' and isinstance(args[0],(str,bytes)) and 'credentials.env' in str(args[0]):
        FORBIDDEN.append(event);raise RuntimeError('offline integration forbids network and credential reads')
sys.addaudithook(deny)
from runner import load_legacy
from bounded import Runtime,MODEL,EMBED,QIDS,read,inheritance
class Fake:
    def __init__(self):self.stages=[]
    def dispatch(self,request,response,seconds):
        state=read(request.parent/'summary.json');e=state['events'][-1];task=read(request);stage=e['stage'];self.stages.append(stage)
        if task['service']=='embedding':value={'model':EMBED,'data':[{'index':0,'embedding':[1.0]*3072}],'usage':{'prompt_tokens':10,'total_tokens':10}}
        else:
            if stage=='primer':text=json.dumps({'intermediate_answer':'Synthetic initial answer.','score':50,'follow_up_queries':[e['cell']+' synthetic branch '+str(i) for i in range(5)]})
            elif stage=='local':text=json.dumps({'response':'Synthetic local answer.','score':50,'follow_up_queries':[]})
            else:text='Synthetic final answer. Not an experiment result.'
            value={'model':MODEL,'choices':[{'finish_reason':'stop','message':{'content':text}}],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}
        return {'http_status':200,'response':value,'request_dispatched':True}
async def main():
    legacy=load_legacy();queries=legacy.verify_protocol();data=legacy.Data();observations=[]
    before=inheritance()[0]
    with tempfile.TemporaryDirectory() as tmp:
        fake=Fake();r=Runtime(Path(tmp)/'run',fake,data.enc,data.eenc,create=True,synthetic=True,wait=lambda _:None)
        for q in queries:
            if q['id'] not in QIDS:continue
            c=r.cell(q['id'],'routed_graphrag','drift');await legacy.execute_cell(data,c,q)
            assert c.data['status']=='complete',c.data.get('failure')
            es=[e for e in r.state['events'] if e['cell']==c.key];gs=Counter(e['stage'] for e in es if e['service']=='generation')
            assert gs=={'primer':1,'local':4,'reduce':1},gs
            inherited=[u for u in c.data['uses'] if u.get('origin_run')]
            assert [u['stage'] for u in inherited]==['hyde','query_embedding']
            primer=next(e for e in es if e['stage']=='primer')
            assert primer['key'] in before['cells'][c.key]['requests']
            observations.append({'qid':q['id'],'synthetic_new_generation_stages':dict(gs),'inherited_cache_uses':len(inherited),'exact_old_primer_key':True})
        r.verify_ledger();r.close()
        again=Runtime(Path(tmp)/'run',fake,data.enc,data.eenc,synthetic=True,wait=lambda _:None);again.verify_ledger();again.close()
    assert inheritance()[0]==before and not FORBIDDEN
    print(json.dumps({'status':'passed','real_official_drift_cells':6,'real_model_calls':0,'credentials_read':False,'old_files_unchanged':True,'observations':observations,'limitation':'Synthetic new answers/embeddings verify software paths only.'},indent=2))
if __name__=='__main__':asyncio.run(main())
