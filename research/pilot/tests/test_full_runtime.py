"""Offline safety/interface checks; no provider calls and no credentials."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import full_runtime as full
import probe_runtime as probe


class FullRuntimeTests(unittest.TestCase):
    def test_message_identity_ignores_only_null_refusal(self):
        a = [{'role': 'assistant', 'content': 'x'}]
        b = [{'role': 'assistant', 'content': 'x', 'refusal': None}]
        self.assertEqual(full.completion_key(a), full.completion_key(b))
        self.assertNotEqual(full.completion_key(a), full.completion_key([{'role': 'assistant', 'content': 'x\n'}]))

    def test_string_prompt_is_user_message(self):
        self.assertEqual(full.normalize_messages('x'), [{'role': 'user', 'content': 'x'}])

    def test_tools_and_refusals_are_not_silently_dropped(self):
        for extra in ({'tool_calls': []}, {'refusal': 'no'}):
            with self.assertRaises(probe.Stop):
                full.normalize_messages([{'role': 'assistant', 'content': 'x', **extra}])

    def test_payload_has_fixed_transport_and_native_schema(self):
        body = probe.generation_payload([{'role': 'user', 'content': 'x'}], probe.REPORT_SCHEMA)
        full.validate_payload('generation', body)
        body['max_output_tokens'] = 99999
        with self.assertRaises(probe.Stop): full.validate_payload('generation', body)

    def test_embedding_identity_includes_exact_text(self):
        self.assertNotEqual(full.embedding_key('x'), full.embedding_key('x\n'))

    def test_fail_closed_exception_escapes_upstream_exception_handler(self):
        self.assertFalse(issubclass(full.Halt, Exception))
        self.assertTrue(issubclass(full.Halt, BaseException))

    def test_complete_over_requested_cap_keeps_authentic_usage(self):
        reply = {'model':probe.MODEL,'choices':[{'finish_reason':'stop','message':{'content':'complete'}}],
                 'usage':{'prompt_tokens':100,'completion_tokens':2278,'total_tokens':2378}}
        content, usage = full.validate_completion(reply, None)
        self.assertEqual(content, 'complete')
        self.assertEqual(usage['completion_tokens'], 2278)
        reply['usage']['total_tokens'] = 0
        with self.assertRaises(probe.Stop): full.validate_completion(reply,None)


if __name__ == '__main__': unittest.main()
