"""One approved HTTP compatibility probe, not a GraphRAG index implementation.

No SDK, retries, redirects, endpoint overrides or resume command. Workers alone
load a task-specific credential. Never print an exception, request, or raw reply.
The persistent run directory is an exclusive, non-resumable batch lock.
"""
import argparse
import ast
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = ROOT / ".cache/pilot/probe-approved-20261012-01"
MS = ROOT / ".cache/ms-graphrag/graphrag-5faaaf4f5685fa2056fa8c3bf9342cb089f2942f"
MODEL = "gpt-5.6-luna"
EMBED = "text-embedding-3-large"
HOSTS = {"generation": "https://one.fullstar.tech/v1/chat/completions",
         "embedding": "https://api.openai.com/v1/embeddings"}
LIMITS = {"generation_attempts": 17, "embedding_attempts": 3,
          "generation_input_tokens": 100000, "embedding_input_tokens": 20000,
          "embedding_items": 21, "generation_output_per_request": 2048,
          "generation_request_seconds": 60, "embedding_request_seconds": 30,
          "wall_seconds": 1200, "rss_bytes": 2 * 1024**3,
          "openai_budget_usd": "0.01", "embedding_usd_per_million": "0.13"}


class Stop(Exception):
    """Only fixed, non-sensitive reason codes belong in this exception."""


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, obj):
    """Atomic private file, fsynced before the associated request may start."""
    temp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(obj, indent=2, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)
    d = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(d)
    finally:
        os.close(d)


class Budget:
    def __init__(self):
        self.counts = {k: 0 for k in ("generation_attempts", "embedding_attempts",
                      "generation_input_tokens", "embedding_input_tokens", "embedding_items")}
        self.stopped = False

    def reserve(self, service, token_counts):
        if self.stopped or service not in HOSTS:
            raise Stop("batch_stopped_or_invalid_service")
        if (not token_counts or any(type(n) is not int or not 0 < n <= 8000 for n in token_counts)
                or (service == "generation" and len(token_counts) != 1)):
            self.stopped = True
            raise Stop("invalid_input_size")
        new = self.counts.copy()
        new[service + "_attempts"] += 1
        new[service + "_input_tokens"] += sum(token_counts)
        if service == "embedding":
            new["embedding_items"] += len(token_counts)
        if any(n > LIMITS[k] for k, n in new.items()):
            self.stopped = True
            raise Stop("budget_would_be_exceeded")
        cost = Decimal(new["embedding_input_tokens"]) * Decimal(LIMITS["embedding_usd_per_million"]) / 1000000
        if cost > Decimal(LIMITS["openai_budget_usd"]):
            self.stopped = True
            raise Stop("openai_budget_would_be_exceeded")
        self.counts = new


def tokenizers():
    import tiktoken
    cache = ROOT / ".cache/pilot/tokenizer"
    for name, sha in [
        ("cl100k_base", "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"),
        ("o200k_base", "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d")]:
        url = f"https://openaipublic.blob.core.windows.net/encodings/{name}.tiktoken"
        p = cache / hashlib.sha1(url.encode()).hexdigest()
        if not p.is_file() or digest(p.read_bytes()) != sha:
            raise Stop("missing_or_changed_cached_tokenizer")
    os.environ["TIKTOKEN_CACHE_DIR"] = str(cache)
    return tiktoken.get_encoding("o200k_base"), tiktoken.get_encoding("cl100k_base")


def prompt_values():
    manifest = json.loads((ROOT / "research/microsoft-version.json").read_text())
    entries = {x["path"]: x for x in manifest["source_files"]}
    values = {}
    for name in ("extract_graph.py", "community_report.py"):
        rel = "packages/graphrag/graphrag/prompts/index/" + name
        p = MS / rel
        if digest(p.read_bytes()) != entries[rel]["sha256"]:
            raise Stop("source_prompt_hash_mismatch")
        for node in ast.parse(p.read_text()).body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                values[node.targets[0].id] = node.value.value
    return values


def generation_payload(messages, schema=None):
    body = {"model": MODEL, "messages": messages, "max_completion_tokens": 2048,
            "stream": False, "num_retries": 0, "fallbacks": [],
            "context_window_fallback_dict": {}, "caching": False}
    if schema is not None:
        body["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "CommunityReportResponse", "strict": True, "schema": schema}}
    return body


REPORT_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["title", "summary", "findings", "rating", "rating_explanation"],
    "properties": {"title": {"type": "string"}, "summary": {"type": "string"},
        "rating": {"type": "number"}, "rating_explanation": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["summary", "explanation"], "properties": {
                "summary": {"type": "string"}, "explanation": {"type": "string"}}}}}}


def validate_payload(service, body):
    if service == "generation":
        expected = generation_payload(body.get("messages", []))
        if "response_format" in body:
            expected = generation_payload(body.get("messages", []), REPORT_SCHEMA)
        if body != expected or not body["messages"]:
            raise Stop("generation_parameters_changed")
        if any(set(m) != {"role", "content"} or m["role"] not in {"user", "assistant"}
               or not isinstance(m["content"], str) for m in body["messages"]):
            raise Stop("unsupported_message")
    elif service == "embedding":
        if (set(body) != {"model", "input", "dimensions", "encoding_format"}
                or body["model"] != EMBED or body["dimensions"] != 3072
                or body["encoding_format"] != "float"
                or not isinstance(body["input"], list)
                or not all(isinstance(s, str) and s for s in body["input"])):
            raise Stop("embedding_parameters_changed")
    else:
        raise Stop("invalid_service")


def load_credential(service):
    """Read only the requested task variable; do not consult environment keys."""
    directory = Path.home() / ".config/code-rag-field-guide"
    d = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    f = None
    try:
        ds = os.fstat(d)
        if ds.st_uid != os.getuid() or stat.S_IMODE(ds.st_mode) != 0o700:
            raise Stop("credential_directory_permissions")
        f = os.open("credentials.env", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=d)
        fs = os.fstat(f)
        if not stat.S_ISREG(fs.st_mode) or fs.st_uid != os.getuid() or stat.S_IMODE(fs.st_mode) != 0o600:
            raise Stop("credential_file_permissions")
        name = "CODE_RAG_FULLSTAR_API_KEY" if service == "generation" else "CODE_RAG_OPENAI_API_KEY"
        values = []
        with os.fdopen(f) as stream:
            f = None
            for line in stream:
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:].lstrip()
                key, sep, value = line.partition("=")
                if sep and key.strip() == name:
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                        value = value[1:-1]
                    else:
                        value = value.split(" #", 1)[0].strip()
                    values.append(value)
        if len(values) != 1 or not values[0] or any(c.isspace() for c in values[0]):
            raise Stop("credential_missing_duplicate_or_invalid")
        return values[0]
    finally:
        if f is not None:
            os.close(f)
        os.close(d)


def error_summary(data):
    """Fixed categories only: never retain server-supplied messages or URLs."""
    try:
        error = json.loads(data).get("error", {})
    except (ValueError, AttributeError):
        return {"response_format": "non_json", "error_category": "unclassified_http_error"}
    if not isinstance(error, dict):
        return {"response_format": "json", "error_category": "unclassified_http_error"}
    allowed = {"invalid_api_key", "invalid_request_error", "model_not_found", "insufficient_quota",
               "rate_limit_exceeded", "unsupported_parameter", "authentication_error", "permission_denied"}
    code = error.get("code")
    message = str(error.get("message", "")).lower()
    category = code if code in allowed else "unclassified_http_error"
    if category == "unclassified_http_error":
        for word, label in [("quota", "quota_related"), ("api key", "authentication_related"),
                            ("model", "model_related"), ("parameter", "parameter_related")]:
            if word in message:
                category = label
                break
    param = error.get("param")
    return {"response_format": "json", "error_category": category,
            "error_parameter": param if param in {"model", "max_completion_tokens", "response_format", "num_retries", "fallbacks"} else None}


def worker(request_path, response_path):
    import ssl
    import urllib.request
    import urllib.error
    import certifi

    class RejectRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise Stop("redirect_rejected")

    try:
        if request_path.parent.resolve() != RUN.resolve() or response_path.parent.resolve() != RUN.resolve():
            return
        ledger = json.loads((RUN / "summary.json").read_text())
        seq = len(ledger["events"])
        if (ledger["status"] != "running" or ledger["supervisor_pid"] != os.getppid()
                or request_path.name != f"request-{seq:02}.json"
                or response_path.name != f"response-{seq:02}.json"
                or ledger["events"][-1]["status"] != "reserved_before_dispatch"):
            return
        task = json.loads(request_path.read_text())
        service, body = task["service"], task["body"]
        validate_payload(service, body)
        if digest(canonical(body).encode()) != ledger["events"][-1]["request_body_sha256"]:
            raise Stop("reserved_payload_changed")
        marker = response_path.with_suffix(".dispatch.json")
        # A used reservation cannot be sent twice, even if a caller invokes --worker.
        marker_fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(marker_fd, "w") as f:
            f.write('{"dispatch_slot_claimed":true}\n')
            f.flush(); os.fsync(f.fileno())
        key = load_credential(service)
        opener = urllib.request.build_opener(RejectRedirect(), urllib.request.HTTPSHandler(
            context=ssl.create_default_context(cafile=certifi.where())))
        req = urllib.request.Request(HOSTS[service], data=canonical(body).encode(), method="POST",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                     "User-Agent": "Mozilla/5.0 (Code-RAG compatibility probe)"})
        def timed_out(signum, frame):
            raise Stop("worker_wall_timeout")
        signal.signal(signal.SIGALRM, timed_out)
        signal.setitimer(signal.ITIMER_REAL, LIMITS[service + "_request_seconds"])
        save(marker, {"dispatch_slot_claimed": True, "dispatch_started": True})
        try:
            with opener.open(req, timeout=LIMITS[service + "_request_seconds"]) as r:
                data = r.read(2 * 1024**2 + 1)
                if len(data) > 2 * 1024**2:
                    raise Stop("response_byte_cap_exceeded")
                # Never retain response headers. Exact credential redaction is a final safeguard.
                parsed = json.loads(data.decode().replace(key, "[REDACTED]"))
                result = {"http_status": r.status, "response": parsed}
        except urllib.error.HTTPError as e:
            result = {"http_status": e.code, **error_summary(e.read(65536))}
        except urllib.error.URLError:
            result = {"error_category": "transport_error"}
        save(response_path, result)
    except Stop as e:
        save(response_path, {"error_category": str(e)})
    except Exception:
        save(response_path, {"error_category": "worker_exception_redacted"})


def rss_bytes(pids):
    # Read only PID/parent/RSS metadata, never process arguments or other projects.
    out = subprocess.check_output(["ps", "-axo", "pid=,ppid=,rss="], text=True)
    rows = [tuple(map(int, line.split())) for line in out.splitlines() if line.strip()]
    descendants = set(pids)
    while True:
        larger = descendants | {pid for pid, parent, rss in rows if parent in descendants}
        if larger == descendants:
            break
        descendants = larger
    return sum(rss for pid, parent, rss in rows if pid in descendants) * 1024


class MemoryWatch:
    """Whole-run sampled RSS threshold; not an instantaneous kernel memory cap."""
    def __init__(self):
        self.done = threading.Event()
        self.peak = 0
        self.reason = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.done.is_set():
            try:
                self.peak = max(self.peak, rss_bytes([os.getpid()]))
                if self.peak >= LIMITS["rss_bytes"]:
                    self.reason = "rss_threshold"
            except Exception:
                self.reason = "rss_monitor_failed"
            if self.reason:
                os.kill(os.getpid(), signal.SIGTERM)
                return
            self.done.wait(0.2)

    def stop(self):
        self.done.set()
        self.thread.join(timeout=2)


def supervise(command, timeout, deadline, memory_probe=rss_bytes):
    started = time.monotonic()
    peak = 0
    proc = subprocess.Popen(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason = None
    try:
        while proc.poll() is None:
            elapsed = time.monotonic() - started
            peak = max(peak, memory_probe([os.getpid(), proc.pid]))
            if peak >= LIMITS["rss_bytes"]:
                reason = "rss_threshold"
            elif elapsed >= timeout or time.monotonic() >= deadline:
                reason = "request_or_batch_timeout"
            if reason:
                os.killpg(proc.pid, signal.SIGKILL)
                break
            time.sleep(min(0.2, timeout / 5))
        proc.wait()
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    return {"supervisor_reason": reason, "worker_exit": proc.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3), "sampled_peak_rss_bytes": peak}


def validate_generation(reply, enc):
    if reply.get("model") != MODEL:
        raise Stop("response_model_mismatch")
    choices = reply.get("choices", [])
    if len(choices) != 1 or choices[0].get("finish_reason") != "stop":
        raise Stop("generation_incomplete_or_multiple_choices")
    content = choices[0].get("message", {}).get("content")
    usage = reply.get("usage", {})
    if not isinstance(content, str) or not content.strip():
        raise Stop("empty_generation")
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("prompt_tokens", "completion_tokens", "total_tokens")):
        raise Stop("missing_or_invalid_generation_usage")
    if usage["completion_tokens"] > 2048 or len(enc.encode(content, disallowed_special=())) > 2048:
        raise Stop("reported_or_visible_output_cap_exceeded")
    if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
        raise Stop("inconsistent_generation_usage")
    return content, {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")}


def parse_extraction(text, chunk_id):
    if not text.rstrip().endswith("<|COMPLETE|>"):
        raise Stop("missing_extraction_completion_marker")
    text = text.rstrip()[:-len("<|COMPLETE|>")].strip().strip("#").strip()
    entities, relations = [], []
    for raw in text.split("##") if text else []:
        raw = raw.strip()
        if not raw.startswith("(") or not raw.endswith(")"):
            raise Stop("malformed_extraction_record")
        fields = [v.strip().strip('"') for v in raw[1:-1].split("<|>")]
        if fields[0] == "entity" and len(fields) == 4:
            if fields[2].lower() not in {"organization", "person", "geo", "event"}:
                raise Stop("unexpected_entity_type")
            row = dict(title=fields[1], type=fields[2], description=fields[3], source_id=chunk_id)
            row["id"] = digest(canonical(row).encode())
            entities.append(row)
        elif fields[0] == "relationship" and len(fields) == 5:
            try:
                weight = float(fields[4])
            except ValueError:
                raise Stop("invalid_relationship_weight") from None
            if not math.isfinite(weight):
                raise Stop("invalid_relationship_weight")
            relations.append(dict(source=fields[1], target=fields[2], description=fields[3], weight=weight))
        else:
            raise Stop("malformed_extraction_fields")
    return entities, relations


def validate_embedding(reply, items, tokens):
    if reply.get("model") != EMBED:
        raise Stop("embedding_model_mismatch")
    data, usage = reply.get("data", []), reply.get("usage", {})
    if usage.get("prompt_tokens") != tokens or usage.get("total_tokens") != tokens:
        raise Stop("embedding_usage_mismatch")
    if len(data) != items or sorted(x.get("index", -1) for x in data) != list(range(items)):
        raise Stop("embedding_item_mismatch")
    for row in data:
        vector = row.get("embedding", [])
        if len(vector) != 3072 or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
            raise Stop("embedding_dimension_or_value_invalid")
    return {"prompt_tokens": tokens, "total_tokens": tokens}


def inputs():
    # Both checks are read-only and offline; no credentials loaded.
    for script, extra in [("verify.py", ["--source"]), ("verify_selection.py", [])]:
        subprocess.run([sys.executable, str(HERE / script), *extra], check=True, stdout=subprocess.DEVNULL)
    rows = {r["id"]: r for r in map(json.loads, (ROOT / ".cache/pilot/input/documents.jsonl").read_text().splitlines())}
    ids = json.loads((HERE / "token-estimate.json").read_text())["compatibility_8_chunks"]["document_ids"]
    queries = [q for q in json.loads((HERE / "questions.json").read_text()) if q["split"] == "dev"]
    if [q["id"] for q in queries] != ["Q03", "Q04", "Q06", "Q11"]:
        raise Stop("dev_ids_changed")
    return [rows[i] for i in ids], queries


def execute():
    started = time.monotonic()
    deadline = started + LIMITS["wall_seconds"]
    watch = MemoryWatch()
    def interrupted(signum, frame):
        raise Stop(watch.reason or "batch_alarm_or_interruption")
    for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    signal.setitimer(signal.ITIMER_REAL, LIMITS["wall_seconds"])
    watch.thread.start()
    chunks, queries = inputs()
    o200k, cl100k = tokenizers()
    prompts = prompt_values()
    RUN.mkdir(mode=0o700)  # Refuses every repeated invocation, including after failure.
    budget, events = Budget(), []
    summary = {"batch_id": RUN.name, "started_utc": datetime.now(timezone.utc).isoformat(),
               "limits": LIMITS, "status": "running", "events": events,
               "supervisor_pid": os.getpid(),
               "implementation": "direct HTTP with fixed Microsoft prompts; GraphRAG/LiteLLM packages not executed"}
    save(RUN / "summary.json", summary)

    def request(service, body, input_ids):
        validate_payload(service, body)
        if time.monotonic() >= deadline:
            raise Stop("batch_deadline")
        counts = ([len(o200k.encode(canonical(body), disallowed_special=()))] if service == "generation"
                  else [len(cl100k.encode(s, disallowed_special=())) for s in body["input"]])
        budget.reserve(service, counts)
        seq = len(events) + 1
        event = {"sequence": seq, "service": service, "input_ids": input_ids,
                 "reserved_input_tokens": sum(counts), "request_body_sha256": digest(canonical(body).encode()),
                 "status": "reserved_before_dispatch"}
        events.append(event)
        summary["reserved"] = budget.counts.copy()
        save(RUN / "summary.json", summary)
        req, res = RUN / f"request-{seq:02}.json", RUN / f"response-{seq:02}.json"
        save(req, {"service": service, "body": body})
        event.update(supervise([sys.executable, str(Path(__file__).resolve()), "--worker", str(req), str(res)],
                               LIMITS[service + "_request_seconds"], deadline))
        marker = res.with_suffix(".dispatch.json")
        event["dispatch_started"] = marker.is_file() and json.loads(marker.read_text()).get("dispatch_started", False)
        if event["supervisor_reason"] or event["worker_exit"] != 0 or not res.is_file():
            raise Stop(event["supervisor_reason"] or "worker_failed")
        result = json.loads(res.read_text())
        event["http_status"] = result.get("http_status")
        if "response" not in result:
            event.update({k: v for k, v in result.items() if k in {"error_category", "error_parameter", "response_format"}})
            raise Stop("http_or_transport_failure")
        response = result["response"]
        model_name = response.get("model")
        event["reported_model"] = (model_name if isinstance(model_name, str) and
            re.fullmatch(r"(?:gpt|text-embedding)-[A-Za-z0-9._-]{1,60}", model_name) else "unrecognized_or_missing")
        usage = response.get("usage", {})
        if isinstance(usage, dict):
            event["reported_usage"] = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                                       if type(usage.get(k)) is int and usage[k] >= 0}
        event["response_model_matches"] = response.get("model") == (MODEL if service == "generation" else EMBED)
        if service == "generation":
            content, usage = validate_generation(response, o200k)
            event.update(usage=usage, visible_output_tokens=len(o200k.encode(content, disallowed_special=())))
            return content, event
        event["usage"] = validate_embedding(response, len(counts), sum(counts))
        event["status"] = "validated"
        save(RUN / "summary.json", summary)
        print(canonical({"sequence": seq, "service": service, "status": "validated", "elapsed_seconds": event["elapsed_seconds"]}), flush=True)
        return None, event

    try:
        entities, relations = [], []
        for chunk in chunks:
            prompt = prompts["GRAPH_EXTRACTION_PROMPT"].format(entity_types="organization,person,geo,event", input_text=chunk["text"])
            messages = [{"role": "user", "content": prompt}]
            for stage in ("initial", "glean"):
                text, event = request("generation", generation_payload(messages), [chunk["id"], stage])
                es, rs = parse_extraction(text, chunk["id"])
                entities.extend(es); relations.extend(rs)
                event.update(status="validated", entity_records=len(es), relationship_records=len(rs))
                save(RUN / "summary.json", summary)
                print(canonical({"sequence": event["sequence"], "service": "generation", "status": "validated", "elapsed_seconds": event["elapsed_seconds"]}), flush=True)
                messages += [{"role": "assistant", "content": text}, {"role": "user", "content": prompts["CONTINUE_PROMPT"]}]
        source = canonical({"entities": entities, "relationships": relations})
        prompt = prompts["COMMUNITY_REPORT_PROMPT"].format(input_text=source, max_report_length=2000)
        text, event = request("generation", generation_payload([{"role": "user", "content": prompt}], REPORT_SCHEMA), ["sample-derived-report"])
        report = json.loads(text)
        if (set(report) != set(REPORT_SCHEMA["required"])
                or any(not isinstance(report[k], str) for k in ("title", "summary", "rating_explanation"))
                or type(report["rating"]) not in (int, float) or not math.isfinite(report["rating"])
                or not isinstance(report["findings"], list)
                or any(not isinstance(f, dict) or set(f) != {"summary", "explanation"}
                       or any(not isinstance(v, str) for v in f.values()) for f in report["findings"])):
            raise Stop("community_report_schema_mismatch")
        event["status"] = "validated"
        save(RUN / "summary.json", summary)
        selected = sorted({e["id"]: e for e in entities if e["description"]}.values(), key=lambda e: e["id"])[:8]
        batches = [([c["text"] for c in chunks], [c["id"] for c in chunks]),
                   ([q["query"] for q in queries], [q["id"] for q in queries]),
                   ([e["description"] for e in selected] + [text], [e["id"] for e in selected] + ["sample-derived-report"])]
        for texts, ids in batches:
            request("embedding", {"model": EMBED, "input": texts, "dimensions": 3072, "encoding_format": "float"}, ids)
        summary["status"] = "compatibility_probe_completed"
    except Stop as e:
        summary.update(status="stopped", stop_reason=str(e))
        if events and events[-1]["status"] == "reserved_before_dispatch":
            events[-1]["status"] = "failed_validation_or_transport"
    except Exception:
        summary.update(status="stopped", stop_reason="unexpected_exception_redacted")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        watch.stop()
        budget.stopped = True
        summary.update(reserved=budget.counts.copy(), elapsed_seconds=round(time.monotonic() - started, 3),
            full_run_sampled_peak_rss_bytes=watch.peak, rss_poll_seconds=0.2,
            finished_utc=datetime.now(timezone.utc).isoformat(), restart_permitted=False,
            openai_reserved_input_cost_usd=str(Decimal(budget.counts["embedding_input_tokens"]) * Decimal("0.13") / 1000000))
        save(RUN / "summary.json", summary)
    print(canonical({"status": summary["status"], "stop_reason": summary.get("stop_reason"),
                     "reserved": summary["reserved"], "elapsed_seconds": summary["elapsed_seconds"]}), flush=True)
    return 0 if summary["status"] == "compatibility_probe_completed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--execute-approved", action="store_true")
    group.add_argument("--worker", nargs=2, metavar=("REQUEST", "RESPONSE"))
    args = parser.parse_args()
    if args.worker:
        worker(*map(Path, args.worker))
        return 0
    if args.check:
        chunks, queries = inputs()
        o200k, cl100k = tokenizers()
        prompts = prompt_values()
        counts = []
        for c in chunks:
            prompt = prompts["GRAPH_EXTRACTION_PROMPT"].format(entity_types="organization,person,geo,event", input_text=c["text"])
            payload = generation_payload([{"role": "user", "content": prompt}])
            validate_payload("generation", payload)
            counts.append(len(o200k.encode(canonical(payload), disallowed_special=())))
        assert max(counts) <= 8000
        known = sum(len(cl100k.encode(x, disallowed_special=())) for x in [c["text"] for c in chunks] + [q["query"] for q in queries])
        assert known == 4327
        print(canonical({"offline_preflight": "passed", "initial_payload_tokens": sum(counts), "known_embedding_tokens": known,
                         "credentials_read": False, "model_requests": 0}))
        return 0
    return execute()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileExistsError:
        print("Batch directory already exists; no restart or resume is permitted.")
        sys.exit(2)
    except Exception:
        print("Preflight failed; details suppressed to avoid private path or credential disclosure.")
        sys.exit(2)
