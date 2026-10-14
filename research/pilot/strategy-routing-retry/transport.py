"""Bounded one-shot HTTPS worker; raw replies retained privately before decoding."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import ssl
import sys
import urllib.error
import urllib.request

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PILOT=HERE.parent
LEGACY=PILOT/'strategy-routing/runtime'
sys.path.insert(0,str(PILOT))
from bounded import Halt, read, save, file_sha, LIMITS, CARRY, inheritance
from responses_decoder import decode_generation, DecodeError
RUN=ROOT/'.cache/pilot/strategy-routing-retry-20261014'
REQUIRED={'bounded.py','transport.py','runner.py','responses_decoder.py','authorization.json','inherited-manifest.json','manual_recovery.py','manual-resume-review.json','transport-stop.json'}

def legacy_transport():
    spec=importlib.util.spec_from_file_location('retry_legacy_transport',LEGACY/'transport.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def check_authorization():
    legacy_transport().check_authorization()
    auth=read(HERE/'authorization.json')
    if (auth['retry_reply_utc']!='2026-10-14T06:19:43+00:00' or auth['retry_reply']!='drift 全部失败了，调查原因并重试'
        or auth['carry']!=CARRY or auth['limits']!=LIMITS or auth['run_directory']!=str(RUN.relative_to(ROOT))):
        raise Halt('retry_authorization_mismatch',fatal=True)
    ready=read(HERE/'live-readiness.json')
    if ready['status']!='independent_review_passed' or not REQUIRED<=set(ready['sha256']):raise Halt('retry_review_incomplete',fatal=True)
    for name,sha in ready['sha256'].items():
        if file_sha(HERE/name)!=sha:raise Halt('retry_reviewed_file_changed',fatal=True)
    inheritance()

class Transport:
    check_authorization=staticmethod(check_authorization)
    def dispatch(self,request,response,seconds):
        import probe_runtime as probe
        check_authorization()
        result=probe.supervise([sys.executable,str(HERE/'transport.py'),'worker',str(request),str(response)],seconds+2,float('inf'))
        marker=response.with_suffix('.dispatch.json')
        dispatched=marker.exists() and read(marker).get('dispatch_started') is True
        if response.exists():return {**read(response),'request_dispatched':dispatched}
        return {'error_category':'request_or_batch_timeout' if result['supervisor_reason']=='request_or_batch_timeout' else 'uncertain_worker_outcome',
                'usage':None,'request_dispatched':dispatched}

def redact(value,key):
    if isinstance(value,str):return value.replace(key,'[REDACTED]')
    if isinstance(value,list):return [redact(x,key) for x in value]
    if isinstance(value,dict):return {redact(k,key):redact(v,key) for k,v in value.items()}
    return value

def sanitize_raw(data,key,content_type):
    # Preserve exact received bytes unless a credential appears literally or
    # as a decoded JSON string (including mixed Unicode escape sequences).
    safe=data.replace(key.encode(),b'[REDACTED]')
    try:
        text=safe.decode('utf8')
        if 'text/event-stream' in content_type.lower() or any(line.startswith('data:') for line in text.splitlines()):
            frames=[];changed=False
            for frame in text.replace('\r\n','\n').split('\n\n'):
                lines=frame.splitlines();payload='\n'.join(x[5:].removeprefix(' ') for x in lines if x.startswith('data:'))
                if payload and payload!='[DONE]':
                    try:
                        obj=json.loads(payload);clean=redact(obj,key)
                        if obj!=clean:
                            frame='\n'.join(x for x in lines if not x.startswith('data:'))+'\ndata: '+json.dumps(clean,ensure_ascii=False);changed=True
                    except ValueError:pass
                frames.append(frame)
            if changed:safe='\n\n'.join(frames).encode()
        else:
            obj=json.loads(text);clean=redact(obj,key)
            if obj!=clean:safe=json.dumps(clean,ensure_ascii=False).encode()
    except (ValueError,UnicodeError):pass
    return safe

def retain_raw(response,data,key,content_type,status,limit):
    """Raw bytes are private, mode 0600; neither headers nor credentials are stored."""
    received_bytes=len(data);original=data;data=sanitize_raw(data,key,content_type)
    raw_path=response.with_suffix('.raw')
    fd=os.open(raw_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    return {'http_status':status,'raw_response_file':raw_path.name,'raw_response_sha256':file_sha(raw_path),
        'response_bytes':received_bytes,'stored_raw_bytes':len(data),'raw_redacted':data!=original,
        'raw_byte_exact':data==original,'response_byte_limit':limit,'raw_complete':received_bytes<=limit,
        'content_type':content_type.split(';')[0] if content_type.split(';')[0] in {'application/json','text/event-stream'} else 'other'}

def worker(request,response):
    import certifi
    import probe_runtime as probe
    from code_prompt_transport import retry_after, connection_category, guarded_error_summary
    check_authorization()
    if request.parent.resolve()!=RUN.resolve() or response.parent.resolve()!=RUN.resolve():raise Halt('retry_worker_directory_mismatch',fatal=True)
    if response.exists():return
    state=read(RUN/'summary.json');seq=len(state['events'])
    if (state['synthetic'] or state['carry']!=CARRY or state['limits']!=LIMITS or state['status']!='running'
        or state['supervisor_pid']!=os.getppid() or request.name!=f'request-{seq:02}.json'
        or response.name!=f'response-{seq:02}.json' or state['events'][-1]['status']!='reserved_before_dispatch'):
        raise Halt('retry_worker_ledger_mismatch',fatal=True)
    task=read(request);service,body=task['service'],task['body'];legacy_transport().validate_payload(service,body)
    payload=json.dumps(body,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if hashlib.sha256(payload).hexdigest()!=state['events'][-1]['request_body_sha256']:raise Halt('reserved_payload_changed',fatal=True)
    marker=response.with_suffix('.dispatch.json')
    fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write('{"dispatch_slot_claimed":true}\n');f.flush();os.fsync(f.fileno())
    result={};limit=(4 if service=='embedding' else 2)*1024**2
    class RejectRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):raise Halt('redirect_rejected',fatal=True)
    def timeout(*args):raise Halt('worker_wall_timeout')
    try:
        key=probe.load_credential(service)
        opener=urllib.request.build_opener(RejectRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())))
        req=urllib.request.Request(probe.HOSTS[service],data=payload,method='POST',headers={
            'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'Mozilla/5.0 (Code-RAG compatibility probe)'})
        signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,LIMITS[service+'_seconds'])
        save(marker,{'dispatch_slot_claimed':True,'dispatch_started':True})
        try:
            with opener.open(req,timeout=LIMITS[service+'_seconds']) as reply:
                data=reply.read(limit+1);ct=reply.headers.get('Content-Type','')
                result=retain_raw(response,data,key,ct,reply.status,limit)
                # Persist raw provenance before attempting a decoder or schema.
                save(response,result)
                if len(data)>limit:raise Halt('response_byte_cap_exceeded')
                raw=data.decode('utf8').replace(key,'[REDACTED]');diagnostics={}
                try:
                    parsed=decode_generation(raw,ct,diagnostics=diagnostics) if service=='generation' else json.loads(raw)
                    result.update(response=redact(parsed,key),transport_diagnostics=diagnostics)
                except DecodeError as error:
                    result.update(error_category=str(error),transport_diagnostics=error.diagnostics)
        except urllib.error.HTTPError as error:
            data=error.read(65537);result=retain_raw(response,data,key,error.headers.get('Content-Type',''),error.code,65536)
            result.update(guarded_error_summary(data,probe.error_summary))
            result.update(retry_after(error.headers.get('Retry-After'),datetime.now(timezone.utc)))
        except (urllib.error.URLError,ConnectionError,TimeoutError) as error:
            result.update(error_category=connection_category(error) or 'transport_error')
            cause=error.reason if isinstance(error,urllib.error.URLError) else error
            reason=getattr(cause,'reason',None)
            # Fixed symbols only, never arbitrary exception messages or URLs.
            result['transport_error_detail']={'class':type(cause).__name__ if type(cause).__name__ in {'SSLError','SSLEOFError','SSLCertVerificationError','SSLZeroReturnError','TimeoutError','ConnectionResetError','ConnectionRefusedError'} else 'other',
                'ssl_reason':reason if isinstance(reason,str) and reason.isascii() and reason.replace('_','').isalnum() and reason.upper()==reason else None,
                'verify_code':getattr(cause,'verify_code',None) if type(getattr(cause,'verify_code',None)) is int else None}
    except Halt as error:result.update(error_category=str(error))
    except probe.Stop as error:result.update(error_category=str(error))
    except Exception:result.update(error_category='worker_exception_redacted')
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        save(response,result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['worker']);p.add_argument('request',type=Path);p.add_argument('response',type=Path)
    a=p.parse_args();worker(a.request,a.response)
