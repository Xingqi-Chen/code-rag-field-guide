"""One approved HTTP compatibility probe, not a GraphRAG index implementation.

No SDK, automatic retries, redirects or endpoint overrides. Workers alone
load a task-specific credential. Never print an exception, request, or raw reply.
The persistent run directory is an exclusive, non-resumable batch lock.
Original batch CLI paths remain disabled; the authorized one-shot has a separate entry point.
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
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = ROOT / ".cache/pilot/probe-approved-20261012-01"
PRIOR_RUN = RUN
KEY_UPDATE_RUN = ROOT / ".cache/pilot/probe-approved-20261012-02"
RESPONSES_RUN = ROOT / ".cache/pilot/probe-approved-20261012-03"
FINISH_RUN = ROOT / ".cache/pilot/probe-approved-20261012-04"
MS = ROOT / ".cache/ms-graphrag/graphrag-5faaaf4f5685fa2056fa8c3bf9342cb089f2942f"
MODEL = "gpt-5.6-luna"
EMBED = "text-embedding-3-large"
HOSTS = {"generation": "https://one.fullstar.tech/v1/responses",
         "embedding": "https://api.openai.com/v1/embeddings"}
LIMITS = {"generation_attempts": 17, "embedding_attempts": 3,
          "generation_input_tokens": 100000, "embedding_input_tokens": 20000,
          "embedding_items": 21, "generation_output_per_request": 2048,
          "generation_request_seconds": 60, "embedding_request_seconds": 30,
          "wall_seconds": 1200,
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
    def __init__(self, inherited=None):
        self.counts = {k: 0 for k in ("generation_attempts", "embedding_attempts",
                      "generation_input_tokens", "embedding_input_tokens", "embedding_items")}
        self.stopped = False
        if inherited is not None:
            if set(inherited) != set(self.counts) or any(type(v) is not int or not 0 <= v <= LIMITS[k] for k, v in inherited.items()):
                raise Stop("invalid_inherited_budget")
            self.counts = inherited.copy()

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
    body = {"model": MODEL, "input": [
                {"role": m["role"], "content": [{
                    "type": "output_text" if m["role"] == "assistant" else "input_text",
                    "text": m["content"]}]} for m in messages],
            "max_output_tokens": 2048, "store": False,
            "stream": True, "num_retries": 0, "fallbacks": [],
            "context_window_fallback_dict": {}, "caching": False}
    if schema is not None:
        body["text"] = {"format": {"type": "json_schema",
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
        try:
            messages = [{"role": m["role"], "content": m["content"][0]["text"]}
                        for m in body["input"]]
        except (KeyError, TypeError, IndexError):
            raise Stop("unsupported_message") from None
        expected = generation_payload(messages, REPORT_SCHEMA if "text" in body else None)
        if body != expected or not messages:
            raise Stop("generation_parameters_changed")
        if any(set(m) != {"role", "content"} or m["role"] not in {"user", "assistant"}
               or not isinstance(m["content"], str) for m in messages):
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


def decode_generation(raw, content_type):
    """Normalize bounded Responses JSON/SSE; partial deltas never prove success.

    No network, SDK, retry, credentials, or retention of auxiliary reasoning.
    The caller still enforces model, usage and visible/reported output limits.
    """
    def obj(text):
        try:
            value = json.loads(text)
        except ValueError:
            raise Stop("responses_invalid_json") from None
        if not isinstance(value, dict):
            raise Stop("responses_invalid_object")
        return value

    items, terminal, response_id = {}, None, None
    sse = "text/event-stream" in (content_type or "").lower() or raw.lstrip().startswith(("data:", "event:"))
    if sse:
        for frame in raw.replace("\r\n", "\n").split("\n\n"):
            data = "\n".join(line[5:].removeprefix(" ") for line in frame.splitlines() if line.startswith("data:"))
            if not data or data == "[DONE]":
                continue
            event = obj(data)
            if terminal is not None:
                raise Stop("responses_after_terminal")
            kind = event.get("type")
            if kind == "error":
                raise Stop("responses_stream_error")
            if "response" in event:
                response = event["response"]
                if (not isinstance(response, dict) or not isinstance(response.get("id"), str)
                        or not response["id"] or response_id not in (None, response["id"])):
                    raise Stop("responses_identity_mismatch")
                response_id = response["id"]
            if kind == "response.output_item.done":
                index, item = event.get("output_index"), event.get("item")
                if (type(index) is not int or index < 0 or index in items
                        or not isinstance(item, dict) or not isinstance(item.get("id"), str)
                        or not item["id"] or any(x["id"] == item["id"] for x in items.values())):
                    raise Stop("responses_invalid_item")
                items[index] = item
            elif kind in {"response.completed", "response.incomplete", "response.failed"}:
                terminal = event.get("response")
                if not isinstance(terminal, dict) or kind != "response." + str(terminal.get("status")):
                    raise Stop("responses_invalid_terminal")
        if terminal is None:
            raise Stop("responses_stream_unfinished")
    else:
        terminal = obj(raw)
    if terminal.get("error") is not None or terminal.get("status") != "completed":
        raise Stop("responses_not_completed")
    output = terminal.get("output")
    if not isinstance(output, list):
        raise Stop("responses_missing_output")
    recovered = not output and bool(items)
    if recovered:
        if sorted(items) != list(range(len(items))):
            raise Stop("responses_item_gap")
        output = [items[i] for i in range(len(items))]
    elif any(i >= len(output) or output[i] != item for i, item in items.items()):
        raise Stop("responses_item_conflict")
    messages = []
    for item in output:
        if not isinstance(item, dict):
            raise Stop("responses_invalid_item")
        if item.get("type") == "reasoning":
            continue  # Never extract, expose or record reasoning content.
        if item.get("type") != "message" or item.get("role") != "assistant" or item.get("status") not in (None, "completed"):
            raise Stop("responses_unexpected_output")
        content = item.get("content")
        if not isinstance(content, list) or not content or any(
                not isinstance(c, dict) or c.get("type") != "output_text" or not isinstance(c.get("text"), str) for c in content):
            raise Stop("responses_nontext_output")
        messages.append("".join(c["text"] for c in content))
    if len(messages) != 1 or not messages[0].strip():
        raise Stop("responses_empty_or_multiple_messages")
    usage = terminal.get("usage")
    if not isinstance(usage, dict):
        raise Stop("responses_missing_usage")
    return {"model": terminal.get("model"),
            "choices": [{"finish_reason": "stop", "message": {"content": messages[0]}}],
            "usage": {"prompt_tokens": usage.get("input_tokens"), "completion_tokens": usage.get("output_tokens"),
                      "total_tokens": usage.get("total_tokens")},
            "responses_transport": "sse" if sse else "json", "recovered_output_items": recovered}


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
            "error_parameter": param if param in {"model", "max_completion_tokens", "max_output_tokens", "response_format", "text", "num_retries", "fallbacks"} else None}


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
        response_byte_limit=(4 if service == "embedding" else 2)*1024**2
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
                data = r.read(response_byte_limit + 1)
                if len(data) > response_byte_limit:
                    raise Stop("response_byte_cap_exceeded")
                # Never retain response headers. Exact credential redaction is a final safeguard.
                raw = data.decode().replace(key, "[REDACTED]")
                parsed = (decode_generation(raw, r.headers.get("Content-Type")) if service == "generation"
                          else json.loads(raw))
                result = {"http_status": r.status, "response": parsed,
                          "response_byte_limit":response_byte_limit,"response_bytes":len(data)}
        except urllib.error.HTTPError as e:
            result = {"http_status": e.code, **error_summary(e.read(65536))}
        except urllib.error.URLError:
            result = {"error_category": "transport_error"}
        save(response_path, result)
    except Stop as e:
        save(response_path, {"error_category": str(e)})
    except Exception:
        save(response_path, {"error_category": "worker_exception_redacted"})


def supervise(command, timeout, deadline):
    started = time.monotonic()
    proc = subprocess.Popen(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    reason = None
    try:
        while proc.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed >= timeout or time.monotonic() >= deadline:
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
            "elapsed_seconds": round(time.monotonic() - started, 3)}


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


def inherited_key_update():
    """One explicit user-authorized continuation, never an automatic retry."""
    prior = json.loads((PRIOR_RUN / "summary.json").read_text())
    public = json.loads((HERE / "probe-result.json").read_text())
    if (prior["status"] != "stopped" or prior["reserved"] != public["reserved"]
            or prior["elapsed_seconds"] != public["elapsed_seconds"]
            or len(prior["events"]) != 1 or prior["events"][0]["http_status"] != 401
            or prior["events"][0]["worker_exit"] != 0):
        raise Stop("prior_batch_not_closed_or_changed")
    try:
        os.kill(prior["supervisor_pid"], 0)
    except ProcessLookupError:
        pass
    else:
        raise Stop("prior_supervisor_still_exists")
    return prior


def execute(key_update=False, finish=False):
    started = time.monotonic()
    prior = inherited_key_update() if key_update else None
    if finish:
        prior = json.loads((RESPONSES_RUN / "summary.json").read_text())
        public = json.loads((HERE / "responses-result.json").read_text())
        if (prior["status"] != "single_glean_validated" or prior["reserved"] != public["reserved"]
                or prior["cumulative_elapsed_seconds"] != public["cumulative_elapsed_seconds"]
                or prior["reserved"]["generation_attempts"] != 4 or prior["reserved"]["embedding_attempts"] != 2):
            raise Stop("prior_responses_batch_not_closed_or_changed")
        try:
            os.kill(prior["supervisor_pid"], 0)
        except ProcessLookupError:
            pass
        else:
            raise Stop("prior_supervisor_still_exists")
    inherited_seconds = (prior["cumulative_elapsed_seconds"] if finish else prior["elapsed_seconds"]) if prior else 0
    remaining_seconds = LIMITS["wall_seconds"] - inherited_seconds
    if remaining_seconds <= 0:
        raise Stop("cumulative_deadline_exhausted")
    deadline = started + remaining_seconds
    def interrupted(signum, frame):
        raise Stop("batch_alarm_or_interruption")
    for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    signal.setitimer(signal.ITIMER_REAL, max(0.001, deadline - time.monotonic()))
    chunks, queries = inputs()
    o200k, cl100k = tokenizers()
    prompts = prompt_values()
    RUN.mkdir(mode=0o700)  # Refuses every repeated invocation, including after failure.
    budget, events = Budget(prior["reserved"] if prior else None), []
    summary = {"batch_id": RUN.name, "started_utc": datetime.now(timezone.utc).isoformat(),
               "limits": LIMITS, "status": "running", "events": events,
               "supervisor_pid": os.getpid(),
               "implementation": "direct HTTP with fixed Microsoft prompts; GraphRAG/LiteLLM packages not executed"}
    if prior:
        summary["inherited"] = {"batch_id": prior["batch_id"], "reserved": prior["reserved"], "elapsed_seconds": inherited_seconds}
        summary["planned_omission"] = ("Fixed chunks 7 and 8 skip glean; reuse chunk 1 and both source/dev embedding batches. Remaining 7 initial + 5 glean + 1 report, then one artifact embedding batch."
                                       if finish else "Last fixed chunk glean omitted to retain report-schema call within 16 remaining generation attempts.")
    summary["executed_source_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
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
                 "cumulative_service_attempt": budget.counts[service + "_attempts"],
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
            event.update(usage=usage, visible_output_tokens=len(o200k.encode(content, disallowed_special=())),
                         terminal_status="completed", responses_transport=response.get("responses_transport"),
                         recovered_output_items=response.get("recovered_output_items"))
            return content, event
        event["usage"] = validate_embedding(response, len(counts), sum(counts))
        event["status"] = "validated"
        save(RUN / "summary.json", summary)
        print(canonical({"sequence": seq, "service": service, "status": "validated", "elapsed_seconds": event["elapsed_seconds"]}), flush=True)
        return None, event

    try:
        entities, relations = [], []
        if finish:
            for folder in (KEY_UPDATE_RUN, RESPONSES_RUN):
                response = json.loads((folder / "response-01.json").read_text())["response"]
                old_text, _ = validate_generation(response, o200k)
                es, rs = parse_extraction(old_text, chunks[0]["id"])
                entities.extend(es); relations.extend(rs)
        for chunk_index, chunk in (enumerate(chunks[1:], 1) if finish else enumerate(chunks)):
            prompt = prompts["GRAPH_EXTRACTION_PROMPT"].format(entity_types="organization,person,geo,event", input_text=chunk["text"])
            messages = [{"role": "user", "content": prompt}]
            stages = ("initial",) if (key_update and chunk_index == 7) or (finish and chunk_index >= 6) else ("initial", "glean")
            for stage in stages:
                text, event = request("generation", generation_payload(messages), [chunk["id"], stage])
                es, rs = parse_extraction(text, chunk["id"])
                entities.extend(es); relations.extend(rs)
                event.update(status="validated", entity_records=len(es), relationship_records=len(rs))
                save(RUN / "summary.json", summary)
                print(canonical({"sequence": event["sequence"], "service": "generation", "status": "validated", "elapsed_seconds": event["elapsed_seconds"]}), flush=True)
                if key_update and chunk_index == 0 and stage == "initial":
                    for texts, ids in [([c["text"] for c in chunks], [c["id"] for c in chunks]),
                                       ([q["query"] for q in queries], [q["id"] for q in queries])]:
                        request("embedding", {"model": EMBED, "input": texts, "dimensions": 3072, "encoding_format": "float"}, ids)
                messages += [{"role": "assistant", "content": text}, {"role": "user", "content": prompts["CONTINUE_PROMPT"]}]
        source = canonical({"entities": entities, "relationships": relations})
        summary["extraction"] = {"entity_records": len(entities), "relationship_records": len(relations),
                                 "initial_chunks_completed": 8, "glean_chunks_completed": 6 if finish else 7 if key_update else 8}
        save(RUN / "extracted-graph.json", {"entities": entities, "relationships": relations})
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
        if key_update or finish:
            batches = batches[2:]
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
        budget.stopped = True
        summary.update(reserved=budget.counts.copy(), elapsed_seconds=round(time.monotonic() - started, 3),
            cumulative_elapsed_seconds=round(inherited_seconds + time.monotonic() - started, 3),
            finished_utc=datetime.now(timezone.utc).isoformat(), restart_permitted=False,
            openai_reserved_input_cost_usd=str(Decimal(budget.counts["embedding_input_tokens"]) * Decimal("0.13") / 1000000))
        save(RUN / "summary.json", summary)
    print(canonical({"status": summary["status"], "stop_reason": summary.get("stop_reason"),
                     "reserved": summary["reserved"], "elapsed_seconds": summary["elapsed_seconds"]}), flush=True)
    return 0 if summary["status"] == "compatibility_probe_completed" else 1


def main():
    global RUN
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--execute-approved", action="store_true")
    group.add_argument("--execute-key-update-20261012", action="store_true")
    group.add_argument("--execute-remaining-approved", action="store_true")
    group.add_argument("--worker", nargs=2, metavar=("REQUEST", "RESPONSE"))
    args = parser.parse_args()
    if args.worker and all(Path(x).parent.resolve() == FINISH_RUN.resolve() for x in args.worker):
        RUN = FINISH_RUN
        worker(*map(Path, args.worker))
        return 0
    if args.execute_remaining_approved:
        RUN = FINISH_RUN
        return execute(finish=True)
    if not args.check:
        print("Responses transport is offline-only pending explicit continuation authorization; no request sent.")
        return 2
    if args.worker:
        if Path(args.worker[0]).parent.resolve() == KEY_UPDATE_RUN.resolve():
            RUN = KEY_UPDATE_RUN
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
    if args.execute_key_update_20261012:
        RUN = KEY_UPDATE_RUN
    return execute(key_update=args.execute_key_update_20261012)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileExistsError:
        print("Batch directory already exists; no restart or resume is permitted.")
        sys.exit(2)
    except Exception:
        print("Preflight failed; details suppressed to avoid private path or credential disclosure.")
        sys.exit(2)
