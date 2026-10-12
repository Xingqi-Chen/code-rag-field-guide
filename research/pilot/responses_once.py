"""Explicitly authorized 2026-10-12: replay one failed glean, no embeddings/retry.

The user accepts that the upstream may ignore the requested output limit.
An exclusive directory prevents repeating this one-shot entry point.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
import probe_runtime as p

p.RUN = p.ROOT / ".cache/pilot/probe-approved-20261012-03"


def run():
    started = time.monotonic()
    prior = json.loads((p.KEY_UPDATE_RUN / "summary.json").read_text())
    public = json.loads((p.HERE / "key-update-result.json").read_text())
    assert prior["status"] == "stopped" and prior["reserved"] == public["reserved"]
    assert prior["cumulative_elapsed_seconds"] == public["cumulative_elapsed_seconds"]
    assert prior["reserved"]["generation_attempts"] == 3 and prior["reserved"]["embedding_attempts"] == 2
    try:
        os.kill(prior["supervisor_pid"], 0)
    except ProcessLookupError:
        pass
    else:
        raise p.Stop("prior_supervisor_still_exists")
    failed = prior["events"][-1]
    assert failed["http_status"] == 500 and failed["input_ids"][1] == "glean"
    original = json.loads((p.KEY_UPDATE_RUN / "request-04.json").read_text())["body"]
    assert p.digest(p.canonical(original).encode()) == failed["request_body_sha256"]
    body = p.generation_payload(original["messages"])
    p.validate_payload("generation", body)
    enc, _ = p.tokenizers()
    budget = p.Budget(prior["reserved"])
    tokens = len(enc.encode(p.canonical(body), disallowed_special=()))
    budget.reserve("generation", [tokens])
    inherited_seconds = prior["cumulative_elapsed_seconds"]
    deadline = started + p.LIMITS["wall_seconds"] - inherited_seconds
    assert deadline > time.monotonic()
    p.RUN.mkdir(mode=0o700)
    event = {"sequence": 1, "service": "generation", "input_ids": failed["input_ids"],
             "cumulative_service_attempt": 4, "reserved_input_tokens": tokens,
             "request_body_sha256": p.digest(p.canonical(body).encode()), "status": "reserved_before_dispatch"}
    summary = {"batch_id": p.RUN.name, "started_utc": datetime.now(timezone.utc).isoformat(),
               "supervisor_pid": os.getpid(), "status": "running", "events": [event],
               "limits": p.LIMITS, "reserved": budget.counts,
               "inherited": {"batch_id": prior["batch_id"], "reserved": prior["reserved"], "cumulative_elapsed_seconds": inherited_seconds},
               "executed_source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=p.ROOT, text=True).strip(),
               "authorization": "One Responses glean only; zero embeddings; upstream output-cap uncertainty explicitly accepted.",
               "implementation": "direct Responses HTTP with unchanged Microsoft prompts; not the GraphRAG package",
               "restart_permitted": False}
    p.save(p.RUN / "summary.json", summary)
    request, response = p.RUN / "request-01.json", p.RUN / "response-01.json"
    p.save(request, {"service": "generation", "body": body})
    try:
        event.update(p.supervise([sys.executable, str(Path(__file__).resolve()), "--worker", str(request), str(response)], 60, deadline))
        marker = response.with_suffix(".dispatch.json")
        event["dispatch_started"] = marker.exists() and json.loads(marker.read_text()).get("dispatch_started", False)
        if event["supervisor_reason"] or event["worker_exit"] != 0 or not response.is_file():
            raise p.Stop(event["supervisor_reason"] or "worker_failed")
        result = json.loads(response.read_text())
        event["http_status"] = result.get("http_status")
        if "response" not in result:
            event.update({k: v for k, v in result.items() if k in {"error_category", "error_parameter", "response_format"}})
            raise p.Stop("http_or_transport_failure")
        reply = result["response"]
        event.update(reported_model=reply.get("model"), reported_usage=reply.get("usage"),
                     terminal_status="completed", responses_transport=reply.get("responses_transport"),
                     recovered_output_items=reply.get("recovered_output_items"))
        text, usage = p.validate_generation(reply, enc)
        entities, relationships = p.parse_extraction(text, failed["input_ids"][0])
        event.update(status="validated", usage=usage, visible_output_tokens=len(enc.encode(text, disallowed_special=())),
                     entity_records=len(entities), relationship_records=len(relationships))
        summary["status"] = "single_glean_validated"
    except p.Stop as e:
        summary.update(status="stopped", stop_reason=str(e))
        event["status"] = "failed_validation_or_transport"
    except Exception:
        summary.update(status="stopped", stop_reason="unexpected_exception_redacted")
        event["status"] = "failed_validation_or_transport"
    finally:
        summary.update(elapsed_seconds=round(time.monotonic() - started, 3),
                       cumulative_elapsed_seconds=round(inherited_seconds + time.monotonic() - started, 3),
                       finished_utc=datetime.now(timezone.utc).isoformat())
        p.save(p.RUN / "summary.json", summary)
    print(p.canonical({k: summary[k] for k in ("status", "reserved", "elapsed_seconds", "cumulative_elapsed_seconds")}))
    print(p.canonical({k: v for k, v in event.items() if k not in {"input_ids", "request_body_sha256"}}))
    return 0 if summary["status"] == "single_glean_validated" else 1


if __name__ == "__main__":
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "--worker":
            p.worker(Path(sys.argv[2]), Path(sys.argv[3]))
            sys.exit(0)
        if sys.argv[1:] != ["--execute-approved-once"]:
            raise p.Stop("explicit_one_shot_flag_required")
        sys.exit(run())
    except Exception:
        print("One-shot preflight stopped; no automatic restart. Details withheld.")
        sys.exit(2)
