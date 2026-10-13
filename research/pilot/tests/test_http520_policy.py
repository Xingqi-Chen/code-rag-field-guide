"""Offline policy boundaries; no request or ledger is made."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import resume_code_prompt_http520 as recovery


def failed(seq,http=520,body='x'):
    return {'sequence':seq,'service':'generation','status':'failed','http_status':http,'error_category':'unclassified_http_error','request_body_sha256':body}


class Http520Tests(unittest.TestCase):
    def test_requires_520_and_stopped_http_error(self):
        for status in [400,401,403,404,408,429,500,502,503,504]:
            self.assertIsNone(recovery.eligibility({'status':'stopped','stop_reason':'unclassified_http_error','events':[failed(1,status)]}))
        self.assertIsNone(recovery.eligibility({'status':'running','stop_reason':'unclassified_http_error','events':[failed(1)]}))

    def test_shared_cap_counts_mixed_errors(self):
        state={'status':'stopped','stop_reason':'unclassified_http_error','events':[failed(1)]}
        self.assertEqual(recovery.eligibility(state)['delay_seconds'],5)
        state['events'].append(failed(2));state['stop_reason']='worker_wall_timeout'
        self.assertEqual(recovery.eligibility(state)['delay_seconds'],15)
        state['events'].append(failed(3));state['stop_reason']='unclassified_http_error'
        self.assertIsNone(recovery.eligibility(state))

    def test_success_blocks_replay_and_administrative_record_not_attempt(self):
        state={'status':'stopped','stop_reason':'unclassified_http_error','events':[failed(1)|{'request_dispatched':False},failed(2)]}
        self.assertEqual(recovery.eligibility(state)['retry_number'],1)
        state['events'].insert(1,failed(0)|{'status':'validated'})
        self.assertIsNone(recovery.eligibility(state))


if __name__=='__main__':unittest.main()
