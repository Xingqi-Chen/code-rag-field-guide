"""No provider or private ledger access: task-scoped retry decision boundaries."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resume_code_prompt_bounded import eligibility


class TimeoutPolicyTests(unittest.TestCase):
    def state(self,n=1):
        return {'status':'stopped','stop_reason':'worker_wall_timeout','events':[
            {'sequence':i+1,'request_body_sha256':'same-body','status':'failed'} for i in range(n)]}

    def test_two_additional_retries_then_stop(self):
        self.assertEqual(eligibility(self.state())['delay_seconds'],5)
        self.assertEqual(eligibility(self.state(2))['delay_seconds'],15)
        self.assertIsNone(eligibility(self.state(3)))

    def test_other_errors_and_total_deadline_do_not_retry(self):
        for reason in ['authentication_error','permission_denied','generation_input_limit',
                       'embedding_dollar_limit','full_run_deadline','transport_error','http_error']:
            state=self.state();state['stop_reason']=reason
            self.assertIsNone(eligibility(state),reason)

    def test_successful_body_is_never_replayed(self):
        state=self.state(2);state['events'][0]['status']='validated'
        self.assertIsNone(eligibility(state))

    def test_supervisor_timeout_needs_specific_evidence(self):
        state=self.state();state['stop_reason']='uncertain_request_no_automatic_replay'
        state['events'][-1]['status']='uncertain_no_response'
        self.assertIsNone(eligibility(state))
        state['events'][-1]['supervisor_reason']='request_or_batch_timeout'
        self.assertEqual(eligibility(state)['retry_number'],1)

    def test_eligibility_is_read_only(self):
        state=self.state();before=deepcopy(state)
        eligibility(state);self.assertEqual(state,before)


if __name__=='__main__':unittest.main()
