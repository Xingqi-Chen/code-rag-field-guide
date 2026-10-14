"""Replay old HyDE/embedding and retry exactly the six failed DRIFT cells."""
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LEGACY=HERE.parent/'strategy-routing/runtime'
sys.path.insert(1,str(LEGACY))
from bounded import Runtime,Halt,read,now,QIDS
from transport import Transport,check_authorization,RUN

def load_legacy():
    spec=importlib.util.spec_from_file_location('legacy_routing_runner',LEGACY/'runner.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

async def execute():
    check_authorization();legacy=load_legacy();queries=legacy.verify_protocol();data=legacy.Data()
    runtime=Runtime(RUN,Transport(),data.enc,data.eenc,create=not RUN.exists())
    runtime.state.setdefault('execution_sessions',[]).append({'started_utc':now(),'python_version':sys.version.split()[0],
        'process_hash_seed':os.environ['PYTHONHASHSEED'],'prior_counts_preserved':runtime.state['counts'].copy()})
    runtime.persist()
    try:
        for q in queries:
            if q['id'] not in QIDS:continue
            if q['route']['method']!='drift':raise Halt('retry_route_changed',fatal=True)
            cell=runtime.cell(q['id'],'routed_graphrag','drift')
            if cell.data['status'] in {'complete','failed'}:continue
            await legacy.execute_cell(data,cell,q)
            print(json.dumps({'event':'retry_cell_finished','question':q['id'],'status':cell.data['status'],
                'failure':cell.data.get('failure'),'cumulative_counts':runtime.state['counts']},ensure_ascii=False),flush=True)
        runtime.state['status']='complete_with_recorded_failures' if any(c['status']=='failed' for c in runtime.state['cells'].values()) else 'complete'
        runtime.verify_ledger();runtime.persist()
    finally:runtime.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['execute']);p.parse_args();asyncio.run(execute())
