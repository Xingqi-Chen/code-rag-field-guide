"""Cheap exact-identifier/AST diagnostics; no gold and no semantic call claims."""
import ast
import json
from pathlib import Path
import re
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'.cache/pilot/source'


def main():
    files=json.loads((HERE/'files.json').read_text())
    definitions=[]
    class Definitions(ast.NodeVisitor):
        def __init__(self,path):self.path=path;self.scope=[]
        def visit_ClassDef(self,node):self.visit_definition(node,'class')
        def visit_FunctionDef(self,node):self.visit_definition(node,'function')
        def visit_AsyncFunctionDef(self,node):self.visit_definition(node,'async_function')
        def visit_definition(self,node,kind):
            definitions.append({'path':self.path,'name':node.name,'qualified_name':'.'.join(self.scope+[node.name]),
                'start_line':node.lineno,'end_line':node.end_lineno,'kind':kind})
            self.scope.append(node.name);self.generic_visit(node);self.scope.pop()
    for item in files:
        if item['path'].endswith('.py'):
            Definitions(item['path']).visit(ast.parse((SOURCE/item['path']).read_text()))
    results=[]
    for q in json.loads((HERE/'questions.json').read_text()):
        t0=time.perf_counter()
        # Use only explicitly written dotted identifiers; no oracle expansion.
        identifiers=list(dict.fromkeys(re.findall(r'\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+',q['query'])))
        matches=[]
        for name in identifiers:
            args=['rg','-n','-F','--',name,*[item['path'] for item in files]]
            result=subprocess.run(args,cwd=SOURCE,text=True,capture_output=True,check=False)
            if result.returncode not in (0,1):raise RuntimeError('rg failed')
            matches.append({'literal':name,'rg_lines':result.stdout.splitlines(),
                'ast_name_candidates':[d for d in definitions if d['name']==name.rsplit('.',1)[-1]]})
        results.append({'question_id':q['id'],'matches':matches,'elapsed_seconds':time.perf_counter()-t0,
                        'status':'literal_reference_only' if identifiers else 'no_explicit_dotted_identifier'})
    destination=HERE/'reference-lookup.json'
    destination.write_text(json.dumps({'scope':'Exact strings from questions and Python AST definition names; not reference binding, a full call graph or scored semantic retrieval.',
        'rg_version':subprocess.check_output(['rg','--version'],text=True).splitlines()[0],
        'definitions_count':len(definitions),'results':results},ensure_ascii=False,indent=2)+'\n')
    print(f'Wrote exact/AST diagnostics for {len(results)} questions, {len(definitions)} definition records; no model calls.')


if __name__=='__main__':main()
