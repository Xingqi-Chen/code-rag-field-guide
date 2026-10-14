"""One reviewed pre-dispatch incident; never resets counters or sends a request."""
from pathlib import Path
import copy
import json
import os
from bounded import Halt,read,save,file_sha,now

HERE=Path(__file__).resolve().parent

def verify_resume_slot(runtime,event,record):
    incident=read(HERE/'supervisor-incident.json')
    receipt=runtime.state.get('non_dispatch_recovery',{})
    if (receipt.get('incident_sha256')!=file_sha(HERE/'supervisor-incident.json') or
        receipt.get('summary_before_sha256')!=incident['summary_before_sha256'] or
        event['sequence']!=1 or event['key']!=incident['request_key'] or
        event.get('request_dispatched') is not False or record['events']!=[1] or
        event['status']!='reviewed_non_dispatch' or event['cell']!='Q01:routed_graphrag' or
        (runtime.directory/'response-01.json').exists() or
        (runtime.directory/'response-01.dispatch.json').exists() or
        file_sha(runtime.directory/'summary-before-supervisor-fix.json')!=incident['summary_before_sha256'] or
        file_sha(runtime.directory/'request-01.json')!=incident['request_sha256']):
        raise Halt('invalid_non_dispatch_recovery',fatal=True)

def apply(runtime,log_path):
    """Called explicitly once, under Runtime's lock and reviewed live gate."""
    incident=read(HERE/'supervisor-incident.json');state=runtime.state
    source=runtime.directory/'summary.json'
    if (file_sha(source)!=incident['summary_before_sha256'] or
        file_sha(log_path)!=incident['log_sha256'] or
        file_sha(runtime.directory/'request-01.json')!=incident['request_sha256'] or
        state['counts']!=incident['counts_retained'] or len(state['events'])!=1 or
        state['status']!='stopped' or state.get('non_dispatch_recovery') or
        state['events'][0]['status']!='uncertain' or
        state['events'][0].get('error_category')!='transport_exception_redacted' or
        set(state['cells'])!={'Q01:routed_graphrag'} or
        set(p.name for p in runtime.directory.iterdir())!={'summary.json','request-01.json','active.lock'}):
        raise Halt('incident_snapshot_mismatch',fatal=True)
    # Write exact immutable-by-convention copies before changing any field.
    for name,body in [('summary-before-supervisor-fix.json',source.read_bytes()),
                      ('log-before-supervisor-fix.txt',Path(log_path).read_bytes())]:
        with open(runtime.directory/name,'xb') as output:
            os.chmod(runtime.directory/name,0o600)
            output.write(body);output.flush();os.fsync(output.fileno())
    event=state['events'][0]
    event['previous_status']='uncertain';event['status']='reviewed_non_dispatch';event['request_dispatched']=False
    state['non_dispatch_recovery']={'incident_sha256':file_sha(HERE/'supervisor-incident.json'),
        'summary_before_sha256':incident['summary_before_sha256'],'applied_utc':now(),
        'counts_before_and_after':copy.deepcopy(state['counts']),
        'action':'Keep reservation 1; permit one fresh reservation for its exact request. Total attempts still <=3.'}
    state['previous_stop_reason']=state.pop('stop_reason');state['status']='running'
    cell=state['cells']['Q01:routed_graphrag']
    cell['previous_failure']=cell.pop('failure');cell.pop('fatal',None);cell['status']='running'
    verify_resume_slot(runtime,event,state['requests'][event['key']]);runtime.persist()

if __name__=='__main__':
    from transport import Transport,check_authorization
    from bounded import Runtime
    import probe_runtime as probe
    check_authorization()
    root=HERE.parents[3];run=root/'.cache/pilot/strategy-routing-20261014'
    if file_sha(run/'summary.json')!=read(HERE/'supervisor-incident.json')['summary_before_sha256']:
        raise Halt('incident_snapshot_mismatch',fatal=True)
    enc,eenc=probe.tokenizers()
    runtime=Runtime(run,Transport(),enc,eenc,adopt_controller=False)
    try:
        apply(runtime,root/'.cache/pilot/strategy-routing-run.log')
        print(json.dumps({'status':'recovered_without_dispatch','counts':runtime.state['counts'],'new_api_calls':0}))
    finally:runtime.close()
