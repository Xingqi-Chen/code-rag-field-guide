"""Offline synthetic interface test of pinned GraphRAG DRIFT orchestration.

Run from the repository with .cache/graphrag-venv/bin/python. No model, network,
credential, index or ledger access occurs. The local context builder is a stub;
this tests the orchestration bound, not retrieval quality or a paid adapter.
Prints JSON; does not write any results itself.
"""
import asyncio
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace as NS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True


def deny_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'http.client.connect', 'urllib.Request'}:
        raise RuntimeError('Offline mock forbids network access')


sys.addaudithook(deny_network)
cache = ROOT / '.cache/pilot/tokenizer'
cache_file = cache / hashlib.sha1(
    b'https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken'
).hexdigest()
assert hashlib.sha256(cache_file.read_bytes()).hexdigest() == '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d'
os.environ['TIKTOKEN_CACHE_DIR'] = str(cache)

from graphrag.config.models.drift_search_config import DRIFTSearchConfig
from graphrag.data_model.community_report import CommunityReport
from graphrag.query.context_builder.builders import ContextBuilderResult
from graphrag.query.structured_search.drift_search.search import DRIFTSearch
from graphrag.query.structured_search.drift_search.drift_context import DRIFTSearchContextBuilder
from graphrag.query.structured_search.drift_search.primer import PrimerResponse
from graphrag_llm.tokenizer.tiktoken_tokenizer import TiktokenTokenizer


class Model:
    tokenizer = TiktokenTokenizer(encoding_name='o200k_base')

    def __init__(self):
        self.calls = []

    async def completion_async(self, **kwargs):
        if kwargs.get('response_format') is PrimerResponse:
            stage = 'primer'
            value = {'intermediate_answer': 'primer answer', 'score': 50,
                     'follow_up_queries': [f'followup {i}' for i in range(5)]}
            content = json.dumps(value)
        elif kwargs.get('stream'):
            stage = 'local'
            content = json.dumps({'response': 'local evidence answer', 'score': 50,
                                  'follow_up_queries': []})
        elif isinstance(kwargs['messages'], str):
            stage, content = 'hyde', 'hypothetical query'
        else:
            stage, content = 'reduce', 'final answer'
        self.calls.append({'stage': stage, 'kwargs': sorted(kwargs),
                           'response_format': kwargs['response_format'].__name__
                           if kwargs.get('response_format') else None})
        if kwargs.get('stream'):
            async def chunks():
                yield NS(choices=[NS(delta=NS(content=content))])
            return chunks()
        return NS(content=content, choices=[NS(message=NS(content=content))],
                  formatted_response=PrimerResponse(**value) if stage == 'primer' else None)


class Embed:
    def __init__(self):
        self.calls = []

    def embedding(self, *, input):
        self.calls.extend(input)
        return NS(first_embedding=[1.0, 0.0])


class LocalContext:
    def __init__(self, embed):
        self.embed = embed

    def build_context(self, query, **kwargs):
        # Mirrors the one query embedding in upstream map_query_to_entities;
        # deliberately does not claim to exercise real vector retrieval here.
        self.embed.embedding(input=[query])
        return ContextBuilderResult(context_chunks='Sources\nid|text\n1|fixed evidence',
                                    context_records={})


async def main():
    assert importlib.metadata.version('graphrag') == '3.3.0'
    import graphrag.query.structured_search.drift_search.search as search
    official = ROOT / '.cache/ms-graphrag/graphrag-5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag'
    assert hashlib.sha256(Path(search.__file__).read_bytes()).digest() == hashlib.sha256(
        (official / 'query/structured_search/drift_search/search.py').read_bytes()).digest()
    random.seed(20261012)
    model, embed = Model(), Embed()
    reports = [CommunityReport(id=str(i), title=f'report{i}', short_id=str(i),
               community_id=str(i), full_content=f'report {i} body',
               full_content_embedding=[1.0, float(i)]) for i in range(3)]
    cfg = DRIFTSearchConfig(drift_k_followups=2, n_depth=2, primer_folds=1, concurrency=1)
    builder = DRIFTSearchContextBuilder(model=model, config=cfg, text_embedder=embed,
        entities=[], entity_text_embeddings=NS(), reports=reports,
        local_mixed_context=LocalContext(embed), tokenizer=model.tokenizer,
        response_type='multiple paragraphs')
    result = await DRIFTSearch(model=model, context_builder=builder,
                              tokenizer=model.tokenizer).search('trace fixed process')
    assert [call['stage'] for call in model.calls] == ['hyde', 'primer', 'local', 'local', 'local', 'local', 'reduce']
    assert len(embed.calls) == 5 and result.llm_calls == 7
    print(json.dumps({'status': 'passed_synthetic_interface_test',
        'official_version': '3.3.0',
        'official_commit': '5faaaf4f5685fa2056fa8c3bf9342cb089f2942f',
        'official_search_sha256': hashlib.sha256(Path(search.__file__).read_bytes()).hexdigest(),
        'config': {'drift_k_followups': 2, 'n_depth': 2, 'primer_folds': 1},
        'generation_calls': len(model.calls), 'generation_stages': dict(Counter(c['stage'] for c in model.calls)),
        'embedding_calls_including_stub_local_queries': len(embed.calls),
        'upstream_reported_generation_calls': result.llm_calls,
        'observed_adapter_arguments': model.calls,
        'new_model_or_embedding_api_calls': 0, 'credentials_read': False,
        'ledger_or_index_written': False,
        'limitations': ['Synthetic responses and reports; no answer-quality evidence.',
            'Local context is a stub; its embedding count is source-checked separately.',
            'HyDE retains official secrets.choice in this mock; the bound is independent of its template choice.',
            'Two epochs may select remaining primer siblings rather than a two-hop chain.',
            'Does not validate the not-yet-implemented paid adapter or its budget enforcement.']}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
