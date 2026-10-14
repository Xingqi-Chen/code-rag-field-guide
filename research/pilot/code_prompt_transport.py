"""Allowlisted transient-error metadata; unchanged payload and one-shot HTTP.

Never retains headers, credentials or error messages. Only parsed Retry-After
and fixed error classes are persisted. TLS, account and safety failures stop.
"""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import errno
import http.client
import json
import math
import socket
import ssl
import urllib.error
import urllib.request


def retry_after(value, now):
    if value is None:return {}
    try:
        if value.strip().isdigit():
            seconds=int(value.strip());until=now+timedelta(seconds=seconds)
        else:
            until=parsedate_to_datetime(value)
            if until.tzinfo is None:raise ValueError('timezone absent')
            seconds=max(0,(until-now).total_seconds())
        if not math.isfinite(seconds):raise ValueError('nonfinite')
        return {'retry_after_seconds':seconds,'retry_not_before_utc':until.astimezone(timezone.utc).isoformat()}
    except (ValueError,TypeError,OverflowError):return {'retry_after_invalid':True}


def connection_category(error):
    reason=error.reason if isinstance(error,urllib.error.URLError) else error
    if isinstance(reason,(ssl.SSLError,ssl.CertificateError)):return 'transport_security_error'
    if isinstance(reason,(TimeoutError,ConnectionError,http.client.RemoteDisconnected,http.client.IncompleteRead)):
        return 'transient_connection_error'
    if isinstance(reason,OSError) and reason.errno in {
        errno.ETIMEDOUT,errno.ECONNRESET,errno.ECONNABORTED,errno.ECONNREFUSED,
        errno.EPIPE,errno.ENETUNREACH,errno.EHOSTUNREACH,socket.EAI_AGAIN}:
        return 'transient_connection_error'
    return None


def guarded_error_summary(data, original):
    result=original(data)
    try:
        error=json.loads(data).get('error',{})
        if not isinstance(error,dict):return result
        text=' '.join(str(error.get(k,'')) for k in ['code','type','message']).lower().replace('_',' ').replace('-',' ')
        guards=[('authentication_related',['api key','api_key','authentication','unauthorized']),
            ('permission_related',['permission','forbidden','access denied','account deactivated','account suspended','account disabled']),
            ('billing_related',['insufficient_quota','quota','balance','credit','billing','payment','funds','余额']),
            ('safety_related',['content filter','content policy','safety','policy violation','policy error'])]
        for category,terms in guards:
            if any(term in text for term in terms):result['error_category']=category;break
    except (ValueError,TypeError,AttributeError):pass
    return result


def run(transport, probe, request, response):
    metadata={}
    original_open=urllib.request.OpenerDirector.open
    original_read=http.client.HTTPResponse.read
    original_error=probe.error_summary
    def capture(error):
        category=connection_category(error)
        if category:metadata['error_category']=category
    def opened(self,*args,**kwargs):
        try:return original_open(self,*args,**kwargs)
        except urllib.error.HTTPError as error:
            metadata.update(retry_after(error.headers.get('Retry-After'),datetime.now(timezone.utc)))
            raise
        except Exception as error:capture(error);raise
    def read(self,*args,**kwargs):
        try:return original_read(self,*args,**kwargs)
        except Exception as error:capture(error);raise
    urllib.request.OpenerDirector.open=opened
    http.client.HTTPResponse.read=read
    probe.error_summary=lambda data:guarded_error_summary(data,original_error)
    try:transport.worker(request,response)
    finally:
        urllib.request.OpenerDirector.open=original_open
        http.client.HTTPResponse.read=original_read
        probe.error_summary=original_error
    if response.exists() and metadata:
        envelope=json.loads(response.read_text())
        # Never transform a successful or safety-rejected response into a retry.
        if envelope.get('http_status')!=200:
            envelope.update(metadata)
            probe.save(response,envelope)
