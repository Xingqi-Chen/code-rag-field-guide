"""Short, offline rejection tests. No credentials, sockets or model calls."""
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "research/pilot/probe_runtime.py"
spec = importlib.util.spec_from_file_location("probe_runtime", path)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class FakeEncoding:
    def encode(self, text, **kwargs):
        return text.split()


class ProbeLimits(unittest.TestCase):
    def test_generation_attempts_and_irreversible_stop(self):
        b = p.Budget()
        for _ in range(17):
            b.reserve("generation", [20])
        with self.assertRaises(p.Stop): b.reserve("generation", [1])
        with self.assertRaises(p.Stop): b.reserve("embedding", [1])
        self.assertEqual(b.counts["generation_attempts"], 17)

    def test_token_caps_independent_of_attempt_caps(self):
        b = p.Budget()
        for _ in range(12): b.reserve("generation", [8000])
        with self.assertRaises(p.Stop): b.reserve("generation", [4001])
        b = p.Budget()
        b.reserve("embedding", [8000, 8000, 4000])
        with self.assertRaises(p.Stop): b.reserve("embedding", [1])
        self.assertEqual(b.counts["embedding_input_tokens"], 20000)

    def test_embedding_batches_items_and_empty_input(self):
        b = p.Budget()
        for _ in range(3): b.reserve("embedding", [1])
        with self.assertRaises(p.Stop): b.reserve("embedding", [1])
        b = p.Budget()
        with self.assertRaises(p.Stop): b.reserve("embedding", [1] * 22)
        with self.assertRaises(p.Stop): p.Budget().reserve("embedding", [0])

    def test_changed_payload_rejected(self):
        original = p.generation_payload([{"role": "user", "content": "fixture"}])
        for key, value in [("model", "other"), ("max_completion_tokens", 2049), ("num_retries", 1), ("fallbacks", ["other"]), ("drop_params", True)]:
            body = dict(original); body[key] = value
            with self.assertRaises(p.Stop): p.validate_payload("generation", body)
        p.validate_payload("generation", original)

    def test_generation_reply_rejections(self):
        reply = {"model": p.MODEL, "choices": [{"finish_reason": "stop", "message": {"content": "<|COMPLETE|>"}}],
                 "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        p.validate_generation(reply, FakeEncoding())
        for mutate in (lambda r: r.update(model="other"), lambda r: r.pop("usage"),
                       lambda r: r["usage"].update(completion_tokens=2049, total_tokens=2050),
                       lambda r: r["choices"][0].update(finish_reason="length")):
            copy = json.loads(json.dumps(reply)); mutate(copy)
            with self.assertRaises(p.Stop): p.validate_generation(copy, FakeEncoding())

    def test_vector_shape_finiteness_and_usage(self):
        reply = {"model": p.EMBED, "usage": {"prompt_tokens": 2, "total_tokens": 2},
                 "data": [{"index": 0, "embedding": [0.0] * 3072}]}
        p.validate_embedding(reply, 1, 2)
        with self.assertRaises(p.Stop): p.validate_embedding(reply, 1, 3)
        reply["data"][0]["embedding"][0] = float("nan")
        with self.assertRaises(p.Stop): p.validate_embedding(reply, 1, 2)

    def test_timeout_and_memory_kill_sleeping_worker(self):
        command = [sys.executable, "-c", "import time; time.sleep(10)"]
        result = p.supervise(command, 0.1, time.monotonic() + 5, memory_probe=lambda _: 1)
        self.assertEqual(result["supervisor_reason"], "request_or_batch_timeout")
        self.assertLess(result["elapsed_seconds"], 2)
        result = p.supervise(command, 5, time.monotonic() + 5, memory_probe=lambda _: 2 * 1024**3)
        self.assertEqual(result["supervisor_reason"], "rss_threshold")
        self.assertNotEqual(result["worker_exit"], 0)

    def test_rss_includes_grandchildren_excludes_unrelated_process(self):
        with patch.object(p.subprocess, "check_output", return_value="10 1 100\n20 10 200\n30 20 300\n40 1 999\n"):
            self.assertEqual(p.rss_bytes([10]), 600 * 1024)

    def test_error_details_do_not_retain_untrusted_strings(self):
        raw = json.dumps({"error": {"message": "api key CREDENTIAL_FIXTURE https://private.invalid/secret", "code": "CREDENTIAL_FIXTURE", "param": "CREDENTIAL_FIXTURE"}}).encode()
        safe = json.dumps(p.error_summary(raw))
        self.assertNotIn("CREDENTIAL_FIXTURE", safe)
        self.assertNotIn("https", safe)
        self.assertEqual(p.parse_extraction("<|COMPLETE|>", "fixture"), ([], []))
        with self.assertRaises(p.Stop): p.parse_extraction("not a record", "fixture")


if __name__ == "__main__":
    unittest.main()
