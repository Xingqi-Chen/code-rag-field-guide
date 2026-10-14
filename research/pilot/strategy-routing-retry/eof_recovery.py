"""Precisely reinterpret confirmed SSLEOFError; preserve historical failure."""
import argparse
from pathlib import Path
from bounded import Halt,read,file_sha,now,retry_delay
HERE=Path(__file__).resolve().parent
STOP_SHA='3028727f2eb161101f371a3f471bca4c2b367e4bf5e1350611e6dc6b42793659'
CELL='Q10:routed_graphrag'

def facts():return read(HERE/'eof-stop.json')
def verify_review():
    review=read(HERE/'eof-review.json')
    if review.get('status')!='independent_review_passed' or review.get('stopped_summary_sha256')!=STOP_SHA:raise Halt('eof_review_missing',fatal=True)
    for name,sha in review['implementation_sha256'].items():
        if file_sha(HERE/name)!=sha:raise Halt('eof_review_changed',fatal=True)

def eligible(runtime,last,record):
    recovery=runtime.state.get('eof_recovery')
    if not recovery or last['sequence']!=15:return False
    verify_review();f=facts();reply=runtime.directory/'response-15.json'
    if (recovery.get('stopped_summary_sha256')!=STOP_SHA or recovery.get('consumed_by') is not None
        or last!=f['event'] or last['cell']!=CELL or last['service']!='generation' or last['stage']!='local'
        or record['events']!=[15] or file_sha(reply)!=f['response_sha256']
        or read(reply).get('transport_error_detail')!={'class':'SSLEOFError','ssl_reason':'UNEXPECTED_EOF_WHILE_READING','verify_code':None}):
        raise Halt('eof_resume_slot_invalid',fatal=True)
    return True

def guard(runtime,cell,service,key):
    recovery=runtime.state.get('eof_recovery')
    if recovery and recovery.get('consumed_by') is None:
        if cell!=CELL or service!='generation' or key!=facts()['event']['key'] or len(runtime.state['events'])!=15:
            raise Halt('eof_resume_requires_exact_first_request',fatal=True)

def prefetch(runtime):
    recovery=runtime.state.get('eof_recovery')
    if recovery and recovery.get('consumed_by') is None:
        key=facts()['event']['key'];runtime.request(CELL,'generation',runtime.state['requests'][key]['body'],'local')

def verify_state(runtime):
    recovery=runtime.state.get('eof_recovery')
    if not recovery:return
    path=runtime.directory/'stopped-summary-event15.json'
    if recovery['stopped_summary_sha256']!=STOP_SHA or file_sha(path)!=STOP_SHA:raise Halt('eof_snapshot_changed',fatal=True)
    before=read(path)
    if runtime.state['events'][:15]!=before['events'] or runtime.state['counts']['generation_reservations']<before['counts']['generation_reservations']:
        raise Halt('eof_history_changed',fatal=True)
    seq=recovery.get('consumed_by')
    if seq is not None:
        if seq!=16 or len(runtime.state['events'])<16 or runtime.state['events'][15].get('reviewed_eof_retry_of')!=15 or runtime.state['events'][15]['key']!=facts()['event']['key']:
            raise Halt('eof_consumption_invalid',fatal=True)
    elif len(runtime.state['events'])!=15:raise Halt('eof_unconsumed_extra_events',fatal=True)

def authorize(runtime):
    verify_review()
    if file_sha(runtime.directory/'summary.json')!=STOP_SHA or file_sha(runtime.directory/'stopped-summary-event15.json')!=STOP_SHA:raise Halt('eof_initial_snapshot_changed',fatal=True)
    if runtime.state['status']!='stopped' or runtime.state.get('stop_reason')!='transport_security_error' or runtime.state.get('eof_recovery'):raise Halt('eof_already_used_or_wrong_stop',fatal=True)
    if runtime.state!=read(runtime.directory/'stopped-summary-event15.json'):raise Halt('eof_state_changed',fatal=True)
    runtime.state['eof_recovery']={'stopped_summary_sha256':STOP_SHA,'event':15,'consumed_by':None,'review_sha256':file_sha(HERE/'eof-review.json'),'reviewed_utc':now(),'scope':'Confirmed abrupt EOF only; fresh connection and original finite transient retry rules; certificate failures remain fatal.'}
    c=runtime.state['cells'][CELL];c.setdefault('historical_stops',[]).append({'failure':c.pop('failure'),'fatal':c.pop('fatal',None),'event':15});c['status']='running'
    runtime.state['historical_eof_stop_reason']=runtime.state.pop('stop_reason');runtime.state['status']='running';runtime.persist()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['authorize']);p.parse_args()
    from transport import RUN,Transport,check_authorization
    from bounded import Runtime
    import probe_runtime
    check_authorization();enc,eenc=probe_runtime.tokenizers();r=Runtime(RUN,Transport(),enc,eenc,adopt_controller=False)
    try:authorize(r)
    finally:r.close()
    print('Confirmed historical EOF reinterpretation recorded; no API call or credential read.')
