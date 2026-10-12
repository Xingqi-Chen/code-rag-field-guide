"""Verify public preparation files, never credentials or an endpoint.

Default mode is standard-library-only for CI. --yaml additionally checks the
candidate configuration with PyYAML; it does not import GraphRAG or LiteLLM.
This is not a runtime budget enforcer or a model compatibility test.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yaml", action="store_true")
    args = parser.parse_args()
    selection = json.loads((HERE / "selection.json").read_text())
    for name, expected in selection["sha256"].items():
        assert Path(name).name == name, "manifest path must be a sibling file"
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == expected, name
    data = json.loads((HERE / "embedding-estimate.json").read_text())
    sample = json.loads((HERE / "token-estimate.json").read_text())["compatibility_8_chunks"]
    assert [x["id"] for x in data["chunks"]] == sample["document_ids"]
    assert [x["id"] for x in data["dev_queries"]] == ["Q03", "Q04", "Q06", "Q11"]
    assert data["encoding"] == "cl100k_base"
    assert sum(x["tokens"] for x in data["chunks"]) == data["chunk_tokens"] == 4247
    assert sum(x["tokens"] for x in data["dev_queries"]) == data["dev_query_tokens"] == 80
    assert data["known_input_tokens"] == data["chunk_tokens"] + data["dev_query_tokens"]
    assert data["remaining_for_generated_artifacts_tokens"] + data["known_input_tokens"] == 20000
    price = Decimal(str(data["standard_usd_per_million_input_tokens"]))
    cap = data["proposed_total_input_token_cap"]
    assert cap == 20000
    assert Decimal(cap) * price / 1000000 == Decimal(str(data["proposed_cap_usd_before_tax"]))
    print(f"Selection hashes ({len(selection['sha256'])} files), frozen 8 IDs / 4 dev queries, token sums and USD arithmetic: PASS.")
    if args.yaml:
        import yaml

        config = yaml.safe_load((HERE / "ms-settings.selected.yaml").read_text())
        generation = config["completion_models"]["default_completion_model"]
        embedding = config["embedding_models"]["default_embedding_model"]
        assert generation["model"] == "gpt-5.6-luna"
        assert generation["api_base"] == "<UNVERIFIED_ONE_FULLSTAR_API_BASE>"
        assert generation["api_key"] == "${CODE_RAG_FULLSTAR_API_KEY}"
        assert generation["call_args"] == dict(max_completion_tokens=2048, timeout=60, num_retries=0, drop_params=False)
        assert embedding["model"] == "text-embedding-3-large"
        assert embedding["api_base"] == "https://api.openai.com/v1"
        assert embedding["api_key"] == "${CODE_RAG_OPENAI_API_KEY}"
        assert embedding["call_args"] == dict(dimensions=3072, timeout=30, num_retries=0, drop_params=False)
        assert generation["retry"]["max_retries"] == embedding["retry"]["max_retries"] == 0
        assert config["concurrent_requests"] == 1 and config["vector_store"]["vector_size"] == 3072
        for method in ("basic_search", "local_search"):
            assert config[method]["embedding_model_id"] == "default_embedding_model"
        print("YAML syntax, selected names, literal key placeholders and candidate request limits: PASS.")
    print("Offline preparation only; no secret loading, model request, runtime limiter or compatibility verification.")


if __name__ == "__main__":
    main()
