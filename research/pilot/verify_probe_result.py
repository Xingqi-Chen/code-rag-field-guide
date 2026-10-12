"""Offline audit of the published probe records; never resumes a batch."""
import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    pin = json.loads((HERE / "runtime-pin.json").read_text())
    for name, sha in pin["sha256"].items():
        assert not Path(name).is_absolute() and ".." not in Path(name).parts
        data = subprocess.check_output(["git", "show", pin["executed_source_commit"] + ":" + name], cwd=ROOT)
        assert hashlib.sha256(data).hexdigest() == sha, name
    result = json.loads((HERE / "probe-result.json").read_text())
    assert result["status"] == "stopped" and result["restart_permitted"] is False
    assert len(result["events"]) == 1
    e = result["events"][0]
    assert e["service"] == "generation" and e["http_status"] == 401
    assert e["dispatch_started"] is True and e["error_category"] == "authentication_related"
    assert e["input_ids"][0] == json.loads((HERE / "token-estimate.json").read_text())["compatibility_8_chunks"]["document_ids"][0]
    assert result["reserved"]["generation_attempts"] == result["generation_http_attempts_sent"] == 1
    assert result["reserved"]["generation_input_tokens"] == e["reserved_input_tokens"] == 2112
    assert result["reserved"]["embedding_attempts"] == result["openai_requests_sent"] == 0
    assert result["reserved"]["embedding_input_tokens"] == 0
    assert result["actual_openai_input_cost_usd"] == "0.00"
    assert result["provider_billed_generation_tokens"] is None
    assert result["provider_generation_charge_usd"] is None
    assert result["elapsed_seconds"] < 1200
    assert "supervisor_pid" not in result
    print("Published probe: pinned runtime, one HTTP 401, zero OpenAI requests, unchanged sample and bounded recorded usage verified offline.")
    continuation_path = HERE / "key-update-result.json"
    if continuation_path.is_file():
        c = json.loads(continuation_path.read_text())
        plan = json.loads((HERE / "key-update-plan.json").read_text())
        for name, sha in plan["sha256"].items():
            data = subprocess.check_output(["git", "show", c["executed_source_commit"] + ":" + name], cwd=ROOT)
            assert hashlib.sha256(data).hexdigest() == sha, name
        assert c["inherited"]["reserved"] == result["reserved"]
        assert c["inherited"]["elapsed_seconds"] == result["elapsed_seconds"]
        for service in ("generation", "embedding"):
            events = [e for e in c["events"] if e["service"] == service]
            assert c["reserved"][service + "_attempts"] == result["reserved"][service + "_attempts"] + len(events)
            assert c["reserved"][service + "_input_tokens"] == result["reserved"][service + "_input_tokens"] + sum(e["reserved_input_tokens"] for e in events)
            assert c["reserved"][service + "_attempts"] <= c["limits"][service + "_attempts"]
            assert c["reserved"][service + "_input_tokens"] <= c["limits"][service + "_input_tokens"]
        assert c["status"] == "stopped" and c["events"][-1]["http_status"] == 500
        assert len(c["events"]) == 4 and c["restart_permitted"] is False
        assert c["reserved"]["generation_attempts"] == 3 and c["reserved"]["embedding_attempts"] == 2
        assert c["openai_reported_input_tokens"] == sum(e["reported_input_tokens"] for e in c["embedding_validation"]) == 4327
        assert all(e["dimensions"] == [3072] and e["all_values_finite"] and e["indexes_complete"] for e in c["embedding_validation"])
        cost = Decimal(c["openai_reported_input_tokens"]) * Decimal("0.13") / 1000000
        assert cost == Decimal(c["openai_input_cost_at_published_rate_usd"]) < Decimal("0.01")
        assert abs(c["cumulative_elapsed_seconds"] - c["elapsed_seconds"] - result["elapsed_seconds"]) < 0.002
        assert c["cumulative_elapsed_seconds"] < 1200
        assert "rss_bytes" not in c["limits"] and "supervisor_pid" not in c
        print("Explicit key-update continuation: inherited totals, HTTP 500 stop, 12 vectors / 4,327 tokens, cost and cumulative time verified offline.")
        once_path = HERE / "responses-result.json"
        if once_path.is_file():
            once = json.loads(once_path.read_text())
            for name, sha in once["executed_source_sha256"].items():
                data = subprocess.check_output(["git", "show", once["executed_source_commit"] + ":" + name], cwd=ROOT)
                assert hashlib.sha256(data).hexdigest() == sha, name
            assert once["inherited"]["reserved"] == c["reserved"] and len(once["events"]) == 1
            e = once["events"][0]
            assert e["service"] == "generation" and e["input_ids"] == c["events"][-1]["input_ids"]
            assert e["http_status"] == 200 and e["terminal_status"] == "completed" and e["status"] == "validated"
            assert e["reported_model"] == "gpt-5.6-luna" and e["responses_transport"] == "sse"
            assert e["usage"] == {"prompt_tokens": 3540, "completion_tokens": 68, "total_tokens": 3608}
            assert e["recovered_output_items"] is False and e["entity_records"] == e["relationship_records"] == 0
            assert once["reserved"]["generation_attempts"] == c["reserved"]["generation_attempts"] + 1 == 4
            assert once["reserved"]["generation_input_tokens"] == c["reserved"]["generation_input_tokens"] + e["reserved_input_tokens"] == 8590
            assert all(once["reserved"][k] == c["reserved"][k] for k in ("embedding_attempts", "embedding_input_tokens", "embedding_items"))
            assert once["new_generation_http_attempts_sent"] == 1 and once["new_embedding_http_attempts_sent"] == 0
            assert abs(once["cumulative_elapsed_seconds"] - c["cumulative_elapsed_seconds"] - once["elapsed_seconds"]) < 0.002
            assert once["elapsed_seconds"] < 60 and once["cumulative_elapsed_seconds"] < 1200
            assert once["status"] == "single_glean_validated" and once["restart_permitted"] is False
            assert "supervisor_pid" not in once
            print("Authorized one-shot Responses glean: one 200/completed, no embeddings/retry, cumulative 4/17 and 2/3 verified offline.")


if __name__ == "__main__":
    main()
