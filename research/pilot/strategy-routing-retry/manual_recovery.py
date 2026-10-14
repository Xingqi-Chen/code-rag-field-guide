"""One reviewed continuation of event12; TLS remains globally nonretryable."""
import argparse
import copy
from pathlib import Path
from bounded import Halt,read,file_sha,now
HERE=Path(__file__).resolve().parent
STOP_SHA='e129ada9670a58b640586618c9d7cd86f833a6a8ffc4fceecb83a78712953ccc'
KEY='5eb2eac01495c36c9a3031d825f99ebca3a6f7295ffcec83a69e758e0502ade0'
BODY_SHA='f8e1af67cf0381e1a73948fe9785951c425725630256ba533a20f7fdd2073df7'
CELL='Q10:routed_graphrag'

def verify_review():
    review=read(HERE/'manual-resume-review.json')
    if review.get('status')!='independent_review_passed' or review.get('stopped_summary_sha256')!=STOP_SHA:
        raise Halt('manual_resume_review_missing',fatal=True)
    for name,sha in review['implementation_sha256'].items():
        if file_sha(HERE/name)!=sha:raise Halt('manual_resume_review_changed',fatal=True)

def eligible(runtime,last,record):
    recovery=runtime.state.get('manual_recovery')
    if not recovery or last['sequence']!=12:return False
    verify_review()
    if (recovery.get('stopped_summary_sha256')!=STOP_SHA or recovery.get('consumed_by') is not None
        or last['cell']!=CELL or last['service']!='embedding' or last['stage']!='query_embedding'
        or last['status']!='failed' or last.get('error_category')!='transport_security_error'
        or last['key']!=KEY or last['request_body_sha256']!=BODY_SHA or record['events']!=[12]):
        raise Halt('manual_resume_slot_invalid',fatal=True)
    return True

def guard_new_reservation(runtime,cell,service,key):
    recovery=runtime.state.get('manual_recovery')
    if recovery and recovery.get('consumed_by') is None:
        if cell!=CELL or service!='embedding' or key!=KEY or len(runtime.state['events'])!=12:
            raise Halt('manual_resume_requires_exact_first_request',fatal=True)

def prefetch(runtime):
    recovery=runtime.state.get('manual_recovery')
    if recovery and recovery.get('consumed_by') is None:
        # Official Local coroutines can arrive in different thread order. Fill
        # only the already authorized failed request's cache before replaying.
        record=runtime.state['requests'][KEY]
        runtime.request(CELL,'embedding',record['body'],'query_embedding')

def verify_state(runtime):
    recovery=runtime.state.get('manual_recovery')
    if not recovery:return
    if recovery['stopped_summary_sha256']!=STOP_SHA or file_sha(runtime.directory/'stopped-summary-event12.json')!=STOP_SHA:
        raise Halt('manual_resume_snapshot_changed',fatal=True)
    before=read(runtime.directory/'stopped-summary-event12.json')
    if runtime.state['events'][:12]!=before['events'] or runtime.state['carry']!=before['carry']:
        raise Halt('manual_resume_history_changed',fatal=True)
    seq=recovery.get('consumed_by')
    if seq is not None:
        if seq!=13 or len(runtime.state['events'])<13 or runtime.state['events'][12].get('manual_retry_of')!=12 or runtime.state['events'][12]['key']!=KEY:
            raise Halt('manual_resume_consumption_invalid',fatal=True)
    elif len(runtime.state['events'])!=12:raise Halt('manual_resume_unconsumed_extra_events',fatal=True)

def authorize(runtime):
    verify_review()
    if file_sha(runtime.directory/'summary.json')!=STOP_SHA or file_sha(runtime.directory/'stopped-summary-event12.json')!=STOP_SHA:
        raise Halt('manual_resume_initial_snapshot_changed',fatal=True)
    if runtime.state['status']!='stopped' or runtime.state.get('stop_reason')!='transport_security_error' or runtime.state.get('manual_recovery'):
        raise Halt('manual_resume_already_used_or_wrong_stop',fatal=True)
    # Runtime construction may adopt the current PID. No other old field changes.
    before=read(runtime.directory/'stopped-summary-event12.json')
    if runtime.state!=before:raise Halt('manual_resume_state_changed',fatal=True)
    runtime.state['manual_recovery']={'stopped_summary_sha256':STOP_SHA,'event':12,'key':KEY,'consumed_by':None,'review_sha256':file_sha(HERE/'manual-resume-review.json'),'reviewed_utc':now(),
        'scope':'Once only. Keep TLS verification and all historical counts. Another TLS failure stops.'}
    c=runtime.state['cells'][CELL];c['historical_stop']={'failure':c.pop('failure'),'fatal':c.pop('fatal',None)};c['status']='running'
    runtime.state['historical_stop_reason']=runtime.state.pop('stop_reason');runtime.state['status']='running';runtime.persist()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['authorize']);p.parse_args()
    from transport import RUN,Transport,check_authorization
    from bounded import Runtime
    import probe_runtime
    check_authorization();enc,eenc=probe_runtime.tokenizers()
    r=Runtime(RUN,Transport(),enc,eenc,adopt_controller=False)
    try:authorize(r)
    finally:r.close()
    print('One event12 continuation recorded; no credential read or API call.')
