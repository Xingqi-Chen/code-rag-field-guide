import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import ssl
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import resume_code_prompt_transient as policy
import code_prompt_transport as transport
import probe_runtime


class TransientPolicyTests(unittest.TestCase):
    def state(self,status=503,category='model_related'):
        event={'sequence':1,'request_body_sha256':'fixed','status':'failed','http_status':status,'error_category':category}
        return {'status':'stopped','stop_reason':category,'events':[event]}

    def test_shared_limit_and_success(self):
        s=self.state();self.assertEqual(policy.eligibility(s)['delay_seconds'],5)
        s['events'].append(dict(s['events'][0],sequence=2,http_status=None,error_category='worker_wall_timeout'))
        self.assertEqual(policy.eligibility(s)['delay_seconds'],15)
        s['events'].append(dict(s['events'][0],sequence=3,http_status=429,error_category='rate_limit_exceeded'))
        self.assertIsNone(policy.eligibility(s))
        s['events']=s['events'][:2];s['events'][0]['status']='validated'
        self.assertIsNone(policy.eligibility(s))

    def test_guarded_failures(self):
        for category in policy.DENIED:
            self.assertIsNone(policy.eligibility(self.state(503,category)))
        for code in [400,401,402,403,404]:self.assertIsNone(policy.eligibility(self.state(code,'unclassified_http_error')))
        s=self.state();s['stop_reason']='generation_attempt_limit';self.assertIsNone(policy.eligibility(s))
        s=self.state();s['events'][0]['retry_after_invalid']=True;self.assertIsNone(policy.eligibility(s))

    def test_allowed_status_and_connection(self):
        for code in [429,500,502,503,504,520,599]:
            self.assertIsNotNone(policy.eligibility(self.state(code,'rate_limit_exceeded' if code==429 else 'unclassified_http_error')))
        self.assertIsNotNone(policy.eligibility(self.state(None,'transient_connection_error')))
        self.assertIsNone(policy.eligibility(self.state(None,'transport_error')))
        self.assertEqual(transport.connection_category(ConnectionResetError()),'transient_connection_error')
        self.assertEqual(transport.connection_category(ssl.SSLError()),'transport_security_error')

    def test_retry_after(self):
        now=datetime(2026,10,14,tzinfo=timezone.utc)
        self.assertEqual(transport.retry_after('90',now)['retry_after_seconds'],90)
        self.assertEqual(transport.retry_after('Wed, 14 Oct 2026 00:02:00 GMT',now)['retry_after_seconds'],120)
        self.assertTrue(transport.retry_after('invalid',now)['retry_after_invalid'])
        s=self.state();s['events'][0]['retry_not_before_utc']=(datetime.now(timezone.utc)+timedelta(seconds=120)).isoformat()
        self.assertGreater(policy.eligibility(s)['delay_seconds'],119)

    def test_sensitive_errors_never_persist_message(self):
        for message,expected in [('account balance exhausted','billing_related'),('permission denied','permission_related'),('invalid api key','authentication_related'),('safety policy violation','safety_related')]:
            result=transport.guarded_error_summary(json.dumps({'error':{'message':message}}),probe_runtime.error_summary)
            self.assertEqual(result['error_category'],expected)
            self.assertNotIn('message',result)
        for field,value,expected in [('code','content_policy_violation','safety_related'),('type','content_policy_error','safety_related'),('code','account_deactivated','permission_related')]:
            result=transport.guarded_error_summary(json.dumps({'error':{field:value}}),probe_runtime.error_summary)
            self.assertEqual(result['error_category'],expected)
            self.assertIsNone(policy.eligibility(self.state(503,result['error_category'])))


if __name__=='__main__':unittest.main()
