"""Synthetic Responses fixtures only: no SDK, sockets, credentials or real replies."""
import copy
import contextlib
import io
import json
from unittest import TestCase, mock
from research.pilot import probe_runtime as p


ITEM = {"id": "fixture-message", "type": "message", "role": "assistant", "status": "completed",
        "content": [{"type": "output_text", "text": "<|COMPLETE|>"}]}
REPLY = {"id": "fixture-response", "model": p.MODEL, "status": "completed", "error": None,
         "output": [ITEM], "usage": {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}}


def sse(*events):
    return "".join("data: " + json.dumps(e) + "\r\n\r\n" for e in events)


def done(item=ITEM, index=0):
    return {"type": "response.output_item.done", "output_index": index, "item": item}


def terminal(reply=REPLY):
    return {"type": "response." + reply["status"], "response": reply}


class Encoding:
    def encode(self, text, **kwargs):
        return text.split()


class ResponsesTransport(TestCase):
    def test_payload_keeps_messages_and_maps_schema_without_changing_prompts(self):
        messages = [{"role": "user", "content": "same initial prompt"},
                    {"role": "assistant", "content": "<|COMPLETE|>"},
                    {"role": "user", "content": "same glean prompt"}]
        body = p.generation_payload(messages)
        p.validate_payload("generation", body)
        self.assertEqual([m["content"][0]["text"] for m in body["input"]], [m["content"] for m in messages])
        self.assertEqual([m["content"][0]["type"] for m in body["input"]], ["input_text", "output_text", "input_text"])
        self.assertEqual(body["max_output_tokens"], 2048)
        self.assertTrue(body["stream"])
        self.assertFalse(body["store"])
        self.assertNotIn("reasoning", body)
        self.assertNotIn("text", body)
        body = p.generation_payload(messages, p.REPORT_SCHEMA)
        p.validate_payload("generation", body)
        self.assertEqual(body["text"]["format"]["schema"], p.REPORT_SCHEMA)

    def test_json_and_populated_sse_have_same_text_usage_and_extraction(self):
        for raw, mime in [(json.dumps(REPLY), "application/json"), (sse(done(), terminal()), "text/event-stream")]:
            normalized = p.decode_generation(raw, mime)
            text, usage = p.validate_generation(normalized, Encoding())
            self.assertEqual(p.parse_extraction(text, "fixture"), ([], []))
            self.assertEqual(usage, {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10})
            self.assertFalse(normalized["recovered_output_items"])

    def test_completed_item_recovers_empty_terminal_and_ignores_deltas(self):
        reply = {**REPLY, "output": []}
        delta = {"type": "response.output_text.delta", "delta": "not final text"}
        result = p.decode_generation(sse(delta, done(), terminal(reply)), "text/event-stream; charset=utf-8")
        self.assertTrue(result["recovered_output_items"])
        self.assertEqual(p.validate_generation(result, Encoding())[0], "<|COMPLETE|>")

    def test_real_empty_and_delta_only_output_fail(self):
        reply = {**REPLY, "output": []}
        for raw, mime in [(json.dumps(reply), "application/json"),
                          (sse({"type": "response.output_text.delta", "delta": "partial"}, terminal(reply)), "text/event-stream")]:
            with self.assertRaisesRegex(p.Stop, "responses_empty_or_multiple_messages"):
                p.decode_generation(raw, mime)

    def test_incomplete_failed_and_disconnected_stream_fail(self):
        for status in ("incomplete", "failed"):
            reply = {**REPLY, "status": status, "incomplete_details": {"reason": "max_output_tokens"}}
            with self.assertRaisesRegex(p.Stop, "responses_not_completed"):
                p.decode_generation(sse(done(), terminal(reply)), "text/event-stream")
        with self.assertRaisesRegex(p.Stop, "responses_stream_unfinished"):
            p.decode_generation(sse(done()) + "data: [DONE]\n\n", "text/event-stream")

    def test_conflicting_duplicate_gapped_or_wrong_identity_items_fail(self):
        altered = copy.deepcopy(ITEM); altered["content"][0]["text"] = "conflict"
        empty = {**REPLY, "output": []}
        cases = [sse(done(altered), terminal()), sse(done(), done(), terminal(empty)),
                 sse(done(index=1), terminal(empty)),
                 sse({"type": "response.created", "response": {"id": "other"}}, terminal()),
                 sse(terminal(), done())]
        for raw in cases:
            with self.assertRaises(p.Stop):
                p.decode_generation(raw, "text/event-stream")

    def test_reasoning_is_excluded_and_missing_usage_or_excess_output_fails(self):
        reply = {**REPLY, "output": [{"type": "reasoning", "id": "fixture-reasoning", "encrypted_content": "OPAQUE_FIXTURE"}, ITEM]}
        normalized = p.decode_generation(json.dumps(reply), "application/json")
        self.assertNotIn("OPAQUE_FIXTURE", json.dumps(normalized))
        for usage in (None, {"input_tokens": 7, "output_tokens": 2049, "total_tokens": 2056}):
            with self.assertRaises(p.Stop):
                p.validate_generation(p.decode_generation(json.dumps({**REPLY, "usage": usage}), "application/json"), Encoding())

    def test_cli_live_paths_remain_disabled_before_credentials_or_dispatch(self):
        for args in (["--execute-approved"], ["--execute-key-update-20261012"], ["--worker", "unused", "unused"]):
            with mock.patch.object(p, "execute", side_effect=AssertionError("dispatch")), \
                 mock.patch.object(p, "worker", side_effect=AssertionError("worker")), \
                 mock.patch("sys.argv", ["probe_runtime.py", *args]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(), 2)
