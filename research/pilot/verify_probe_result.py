"""Offline audit of the published first-probe record; never resumes a batch."""
import hashlib
import json
import subprocess
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


if __name__ == "__main__":
    main()
