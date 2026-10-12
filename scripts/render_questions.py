"""Render the frozen question/evidence manifest without copying corpus code."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
repos={r['name']:r for r in json.loads((ROOT/'benchmark/corpora.json').read_text())}
qs=json.loads((ROOT/'benchmark/queries.json').read_text())
lines=['# 冻结题目与可检查证据','','检索只使用英文query。中文为原创释义；链接固定到语料commit。关键行是最低检查锚点，不等于完整回答。标注由研究代理静态审阅完成，未经过外部人类标注员复核。','']
for q in qs:
    lines += [f"## {q['id']} · {q['category']}",'',q['question_zh'],'',f"> {q['query']}",'']
    r=repos[q['repo']]
    for e in q['evidence']:
        url=f"{r['url']}/blob/{r['commit']}/{e['path']}#L{e['line']}"
        lines.append(f"- [{e['path']}:{e['line']}]({url})：{e['note']}")
    if not q['evidence']: lines.append('负例边界：'+q['negative_rationale'])
    lines.append('')
(ROOT/'benchmark/questions.md').write_text('\n'.join(lines).rstrip()+'\n')
