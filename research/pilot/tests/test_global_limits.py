"""Fail-closed checks before any transport; no SDK, network or credentials."""
import asyncio
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import global_experiment as g


class Encoder:
    def encode(self,s):return list(s)


class GlobalLimits(unittest.TestCase):
    def runtime(self):
        r=g.Runtime.__new__(g.Runtime)
        r.enc=Encoder();r.started=time.monotonic()
        r.ledger={'status':'running','events':[],'input_content_tokens':0}
        r.save=lambda:None
        return r

    def test_embedding_is_forbidden(self):
        with self.assertRaises(g.probe.Stop):g.validate_payload('embedding',{})

    def test_attempt_limit_stops_before_request(self):
        r=self.runtime();r.ledger['events']=[{}]*60
        with self.assertRaises(g.Halt):r.complete('test')
        self.assertEqual(r.ledger['status'],'stopped')

    def test_input_and_wall_limits_stop_before_request(self):
        for kind in ['per_request','aggregate','wall']:
            r=self.runtime();prompt='test'
            if kind=='per_request':prompt='x'*16001
            if kind=='aggregate':r.ledger['input_content_tokens']=864000
            if kind=='wall':r.started-=3601
            with self.assertRaises(g.Halt):r.complete(prompt)
            self.assertEqual(r.ledger['events'],[])

    def test_duplicate_cannot_replay(self):
        r=self.runtime();body=g.probe.generation_payload([{'role':'user','content':'test'}])
        r.ledger['events']=[{'request_body_sha256':g.sha(g.probe.canonical(body).encode())}]
        with self.assertRaises(g.Halt):r.complete('test')
        self.assertEqual(r.ledger['stop_reason'],'global_duplicate_request_forbidden')

    def test_first_stop_reason_and_adapter_escape(self):
        r=self.runtime()
        with self.assertRaises(g.Halt):r.fail('first')
        with self.assertRaisesRegex(g.Halt,'first'):r.fail('second')
        r=self.runtime()
        def broken(*a,**kw):raise ValueError('synthetic')
        r.complete=broken
        with self.assertRaisesRegex(g.Halt,'global_adapter_exception_redacted'):
            asyncio.run(g.Adapter(r).completion_async(messages=[]))


if __name__=='__main__':unittest.main()
