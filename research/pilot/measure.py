"""Static token/request estimates; no model imports, endpoints, or dollar guesses."""
import ast
import hashlib
import json
import os
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
os.environ.setdefault('TIKTOKEN_CACHE_DIR',str(ROOT/'.cache/pilot/tokenizer'))
import tiktoken
enc=tiktoken.get_encoding('o200k_base')
count=lambda s:len(enc.encode(s,disallowed_special=()))
ms=ROOT/'.cache/ms-graphrag/graphrag-5faaaf4f5685fa2056fa8c3bf9342cb089f2942f'
prompt_path=ms/'packages/graphrag/graphrag/prompts/index/extract_graph.py'
values={}
for node in ast.parse(prompt_path.read_text()).body:
    if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
        values[node.targets[0].id]=node.value.value
rows=[json.loads(s) for s in (ROOT/'.cache/pilot/input/documents.jsonl').read_text().splitlines()]
ordered=sorted(rows,key=lambda r:hashlib.sha256(('20261012:'+r['id']).encode()).hexdigest())
answer={'unit':'o200k_base text tokens, not provider billing tokens',
        'prompt_sha256':hashlib.sha256(prompt_path.read_bytes()).hexdigest(),
        'output_cap_assumption_per_request':2048,
        'cap_status':'estimation assumption only; real endpoint/output/retry caps must be approved and implemented',
        'excludes':'message framing, description summaries, community reports, retries, embedding graph artifacts, editing',
        'actual_model_calls':0}
for label,subset in [('compatibility_8_chunks',ordered[:8]),('full_114_chunks',rows)]:
    n=len(subset)
    initial=sum(count(values['GRAPH_EXTRACTION_PROMPT'].format(entity_types='organization,person,geo,event',input_text=r['text'])) for r in subset)
    cont=count(values['CONTINUE_PROMPT'])*n
    answer[label]={'chunks':n,'chunk_text_tokens':sum(count(r['text']) for r in subset),
                   'initial_extraction_prompt_tokens':initial,'logical_completion_calls_if_all_successful':2*n,
                   'extraction_input_text_token_range':[2*initial+cont,2*initial+cont+n*2048],
                   'extraction_output_text_token_range':[0,2*n*2048]}
    if n==8:answer[label]['document_ids']=[r['id'] for r in subset]
questions=json.loads((HERE/'questions.json').read_text())+json.loads((HERE/'features.json').read_text())
answer['query_text_tokens_22']=sum(count(q['query']) for q in questions)
print(json.dumps(answer,ensure_ascii=False,indent=2))
