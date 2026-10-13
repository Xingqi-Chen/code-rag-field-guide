"""Offline tests for removing only the stage timer and a no-dispatch checkpoint."""
from pathlib import Path
import math
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import full_runtime
import resume_code_prompt_no_deadline as resumed


class DeadlineRemovalTests(unittest.TestCase):
    def test_total_deadline_can_be_absent_without_changing_request_cap(self):
        runtime=full_runtime.Runtime.__new__(full_runtime.Runtime)
        runtime.ledger={'wall_deadline_removed':True,'started_utc':'2026-10-13T13:12:59.674100+00:00'}
        self.assertTrue(math.isinf(runtime.remaining_seconds()))
        self.assertEqual(resumed.POLICY['generation_request_seconds'],120)
        self.assertEqual(resumed.POLICY['embedding_request_seconds'],30)
        self.assertEqual(resumed.POLICY['max_additional_retries_per_request_hash'],2)

    def test_checkpoint_requires_proof_of_no_dispatch(self):
        state={'status':'stopped','stop_reason':'authorized_deadline_policy_checkpoint',
               'events':[{'sequence':180,'status':'failed','request_body_sha256':'x'}]}
        self.assertIsNone(resumed.eligibility(state))
        state['events'][-1].update(request_dispatched=False,policy_checkpoint=True)
        self.assertEqual(resumed.eligibility(state)['retry_number'],0)

    def test_checkpoint_does_not_consume_physical_retry_slot(self):
        checkpoint={'sequence':180,'status':'failed','request_body_sha256':'x','request_dispatched':False}
        one={'sequence':181,'status':'failed','request_body_sha256':'x'}
        state={'status':'stopped','stop_reason':'worker_wall_timeout','events':[checkpoint,one]}
        self.assertEqual(resumed.eligibility(state)['retry_number'],1)
        state['events'].append({**one,'sequence':182})
        self.assertEqual(resumed.eligibility(state)['retry_number'],2)
        state['events'].append({**one,'sequence':183})
        self.assertIsNone(resumed.eligibility(state))


if __name__=='__main__':unittest.main()
