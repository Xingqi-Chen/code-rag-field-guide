# 代码提示词＋实体类型：已完成结果与复算

固定Requests快照、114块、20题及gold，Microsoft GraphRAG v3.3.0。在线索引于2026-10-14 02:42:38 UTC完成；80份新Local上下文已离线构建，与320份未改动基线合并为400行评分。**新配置改善Local覆盖，仍低于hybrid；16000档MRR和Recall@5更好。** 可先读[主报告](../../../../docs/report.md)。

| 必要源码证据覆盖，15道可评分test | 4000 | 8000 | 12000 | 16000 |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 35.3% | 43.7% | 64.3% | 69.3% |
| hybrid | 42.9% | 56.3% | 71.0% | 77.9% |
| Basic | 35.8% | 55.8% | 57.4% | 57.4% |
| Local：默认抽取 | 5.6% | 21.0% | 21.0% | 23.2% |
| Local：代码提示词＋实体类型 | 19.0% | 42.2% | 53.8% | 55.4% |

16000档新Local MRR为0.618889、Recall@5为0.537778；hybrid为0.527906、0.484444。前排优势不等于找全。新Local与hybrid的按16道test平均的实际源码量约7398／14666 token，固定上限不是等量原文。覆盖80%行与100%行口径在全部400行得到相同结果；Q19无gold不计召回，4道dev单列。不是回答正确率。

## 阅读顺序

- [完成状态](evaluation-completion.json)：索引快照与后来离线评分的独立完成记录。`execution.json`的`evaluation_complete:false`是**索引完成时的快照**，保持原样；不是当前评分未完成。
- [逐题分数](scores.json)、[配对／题型／成本汇总](analysis.json)：400行原始评分，60个方法／预算／split汇总；对比不改gold。
- [80份实际材料](contexts)、[检索清单](retrieval.json)：原官方上下文、实际序列化文本、来源行号、token及耗时。外部调用0，所有`dropped_tail_rows=0`。
- [实体](index/entities.json)、[关系](index/relationships.json)、[社区](index/communities.json)、[报告分页清单](index/community_reports.json)：不删字段或记录；大表分页有逐页及整表逻辑hash，使用`index_artifacts.read_table`重组验证。
- [索引规模](index-summary.json)、[运行账本](execution.json)、[共享向量缓存hash](imported-embedding-cache.json)、[源码来源](provenance.json)。公开产物不含权重、向量缓存、凭据或完整第三方仓库。
- [固定案例图层检查](fixed-graph-review.json)、[Local最终链路检查](fixed-local-review.json)：Q01仍缺实现，Q07补到Session中段，Q13补到部分测试与消费者；G02只检查图／报告，未生成新答案。
- [按hash选的样本](quality-sample.json)、[新图逐条AI审阅](quality-review-code-prompt.json)、[旧图逐条AI审阅](quality-review-default.json)：各20实体＋20关系，不是全图精度或人类盲评。
- [抽取见证](extraction-witnesses.json)、[初抽／补抽拼接诊断](concatenation-diagnostics.json)：分别解析与官方拼接解析的记录差，未据此修图／重评。
- [最终独立审计](final-evaluation-review.json)、[原报告格式审计](report-format-audit.json)：数值、来源、预算、运行边界及官方宽松解析的局限。

## 实际成本与不确定性

1628实体、2891关系、372份报告；110/114块有实体关联。1349个生成预算预留中有2个从未派发（195、675），因此实际生成尝试1347次。初抽119、补抽114、描述740、报告374；有效初抽／补抽各114，描述738、报告372。另103批新embedding。缓存命中8434次不能加成新调用。

已知生成usage为4134333输入、1132190输出token；事件75、96、107、108、109、272、623、1207、1248缺模型usage，保持未知。新embedding451878 token，加此前206333累计658211；按记录单价估计累计$0.08556743，非账单。生成费用未知。

已记录请求时间合计12384.287秒（206.40分钟），554耗时缺失；workflow累计13036.603秒含554未知停机区间，不是精确计算耗时。已识别停止／恢复间隔35541.479秒，首次启动至完成48579.016秒（13.49小时）；中断、诊断与等待不能全部归为算法或授权等待。输出31645402字节、其中向量26929820；新配置另启用435918字节原始图快照用于审计，默认未单列此项。内存按用户要求未采样。

新配置是在看过旧失败后设计；提示词与实体类型一起变更，没有新独立保留题，没有等实际源码预算／随机邻居消融。运行时限60→120秒、取消总截止、临时重试与1200→1600次数上限变更均披露。因此只报告本次配置差异，不宣称提示词或图的独立因果收益。

## 格式与恢复记录

三份不同完整报告做了获授权的最小纯JSON修复，均从原缓存副本处理，原响应／缓存／usage不变、无完整响应重发：

| 回复事件 | 实际处理 | 审计 |
| --- | --- | --- |
| 1027 | 删除4个字符串外尾逗号 | [原文及精确差异](schema-1027-diagnosis.json)、[单次授权](schema-1027-amendment.json) |
| 1091 | 删除字符串外尾逗号 | [诊断](schema-1091-diagnosis.json)、[运行范围政策](json-tail-comma-amendment.json)、[实际记录](json-syntax-repairs/event-1091.json) |
| 1147 | 插入4个JSON转义反斜线，保留原有双重引号代码文本 | [原文及精确候选](schema-1147-diagnosis.json)、[后续同类最小格式政策](json-format-amendment.json)、[实际记录](json-format-repairs/event-1147.json) |

三者分别被恢复流程从缓存应用5／4／3次，不是12个不同回复。允许规则只处理确定的最小格式问题，通过原schema、拒绝重复字段和语义修改；不修函数名或代码含义。[独立恢复审阅](json-format-resume-review.json)

另有4份未经修复的报告被官方宽松解析接受：1062有同值重复`explanation`；1253有不同值重复`explanation`，后值覆盖前值；1117有空字段名、1292有额外`source`字段，模型解析忽略额外字段。372份中370过原请求schema、368过严格唯一键schema；默认84份三种口径均通过。它们不计入3条修复，不补修或重跑；详见[全量格式审计](report-format-audit.json)。格式通过也不证明内容正确。

13次中断快照`execution-interrupted*.json`、各次amendment／recovery及[过程日志](../../../process.md)保留历史。第554次完整回复离线验证后复用，实际停机端点未知；1207、1248连接错误在既定有界重试规则内恢复。历史诊断中的“未批准”“未完成”或候选`applied:false`描述的是当时状态，不覆盖本页最终状态。

## 不调用模型的复算

在仓库根目录执行，以下仅需Python标准库：

```bash
python3 research/pilot/verify_code_prompt.py
python3 research/pilot/verify_code_prompt_completed.py
python3 research/pilot/evaluate_code_prompt.py check
python3 research/pilot/analyze_code_prompt.py --check
python3 research/pilot/complete_code_prompt_evaluation.py --check
python3 scripts/validate.py
```

如已安装[固定运行环境](../../full-run.md)，可以额外按真实`o200k_base`重数token：

```bash
.cache/graphrag-venv/bin/python research/pilot/evaluate_code_prompt.py check --tokens
```

离线检索实际命令是`evaluate_code_prompt.py retrieve`，使用既有私有parquet索引和134份缓存向量；它拒绝覆盖已有contexts，并有禁止网络审计钩子。已有80份结果无需重新检索即可复算评分。在线建图命令及授权边界见[执行前冻结包](../../code-prompt/README.md)；远端随机生成不保证重跑图完全相同，不能把评分可复算称为生成过程逐字确定。
