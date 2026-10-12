"""Count the frozen smoke-test inputs locally; no credentials or model requests.

Requires the small, public cl100k_base vocabulary already in the task cache.
This script deliberately refuses to download missing files.
"""
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VOCAB_URL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
VOCAB_SHA256 = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"


def main():
    cache = ROOT / ".cache/pilot/tokenizer"
    vocab = cache / hashlib.sha1(VOCAB_URL.encode()).hexdigest()
    if not vocab.is_file() or hashlib.sha256(vocab.read_bytes()).hexdigest() != VOCAB_SHA256:
        raise SystemExit("Missing or changed public cl100k_base vocabulary; see probe.md.")
    os.environ["TIKTOKEN_CACHE_DIR"] = str(cache)
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    count = lambda text: len(enc.encode(text, disallowed_special=()))
    source = ROOT / ".cache/pilot/input/documents.jsonl"
    rows = {row["id"]: row for row in map(json.loads, source.read_text().splitlines())}
    ids = json.loads((HERE / "token-estimate.json").read_text())["compatibility_8_chunks"]["document_ids"]
    questions = json.loads((HERE / "questions.json").read_text())
    dev = [q for q in questions if q["split"] == "dev"]
    assert [q["id"] for q in dev] == ["Q03", "Q04", "Q06", "Q11"]
    chunks = [{"id": i, "tokens": count(rows[i]["text"])} for i in ids]
    queries = [{"id": q["id"], "tokens": count(q["query"])} for q in dev]
    known = sum(r["tokens"] for r in chunks + queries)
    assert all(0 < r["tokens"] <= 8000 for r in chunks + queries)
    assert known <= 20000
    print(json.dumps({
        "status": "local token measurement only; actual model calls: 0",
        "encoding": "cl100k_base", "tiktoken_version": tiktoken.__version__,
        "vocabulary_url": VOCAB_URL, "vocabulary_sha256": VOCAB_SHA256,
        "input_jsonl_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "chunks": chunks, "dev_queries": queries,
        "chunk_tokens": sum(r["tokens"] for r in chunks),
        "dev_query_tokens": sum(r["tokens"] for r in queries),
        "known_input_tokens": known,
        "proposed_total_input_token_cap": 20000,
        "remaining_for_generated_artifacts_tokens": 20000 - known,
        "standard_usd_per_million_input_tokens": 0.13,
        "proposed_cap_usd_before_tax": 0.0026,
        "price_checked_on": "2026-10-12",
        "price_source": "https://developers.openai.com/api/docs/models/text-embedding-3-large"
    }, indent=2))


if __name__ == "__main__":
    main()
