# 8块兼容性探测：待批准的明确范围

**这是执行前的范围与限额，尚未发出任何模型请求。** 2026-10-12用户已选生成服务 one.fullstar.tech／`gpt-5.6-luna`，统一embedding选 OpenAI官方／`text-embedding-3-large`，默认3072维。模型选择没有改变冻结题目、证据或评分协议，也没有更改本任务自身使用的开发模型。

可以把这一步理解成通水试验：先看接口能否接通、输出格式是否符合要求、向量是否完整。它不能说明图检索更准，也不会自动扩大为114块完整索引。

## 一次探测最多做什么

复用原先按种子20261012选出的[同8块ID](token-estimate.json)，不另挑样本，不读取test问题或gold给模型。只对4条dev查询做embedding，不评分、不调参。

| 项目 | 一次探测的上限 |
| --- | --- |
| 生成调用 | **17次实际发送尝试**：8块各初抽1次、补抽1次，另1次社区报告JSON字段兼容检查；失败也计数 |
| 生成输出 | 每次请求 `max_completion_tokens=2048`；最多请求34,816输出token额度；返回可见文本另按 `o200k_base` 检查≤2048，超出即停 |
| 生成输入 | 所有消息／schema的序列化文本累计≤100,000个 `o200k_base` token；每次≤8,000；这是共同计数口径，不假称第三方账单token |
| 生成超时与重试 | 每次总等待≤60秒；GraphRAG、LiteLLM、传输层均0次自动重试；不自动换模型、接口或放宽参数 |
| embedding调用 | **最多3次实际发送尝试**：8源码块一批、4dev查询一批、最多8条实体描述与1份报告一批；最多21段 |
| embedding输入 | 累计≤**20,000个 `cl100k_base` token**；每段1–8,000；不截断、不拆出额外批次、不因失败退回已预留额度 |
| embedding输出 | 每段必须返回3072个有限数值，数目、index、模型标识与usage需核对；三组以后共用同一缓存键规则 |
| embedding超时与重试 | 每次总等待≤30秒；所有层0次自动重试 |
| 整体资源 | 并发1；从探测进程启动到结束≤20分钟；进程树RSS达到2GiB即中止；不下载模型权重 |

第三次embedding是数据相关的可选步骤：把本次抽取产物按稳定ID排序，取前8条非空实体描述和通过格式检查的那1份报告。它只检查图产物能否向量化；不是正式检索样本选择规则。若产物不足则少做，若剩余额度不足则停止并报告部分完成，不能重选更便宜的材料后继续。

Local需要实体描述embedding；社区报告embedding是本模板的额外选择，Local上下文构建本身不依赖它。完整索引的实体／报告数量仍未知，不能从本次3批上限外推完整索引费用，见[固定接口说明](interfaces.md)。

第17次生成只检查固定版社区报告要求的 `title`、`summary`、`findings`（含summary/explanation）、`rating`、`rating_explanation` 字段，输入限于这8块产生的材料。**它不运行完整社区划分、描述汇总或报告流水线**。冻结版默认实体类型与抽取prompt保持原样，返回不符合预期就记录失败，不能在此轮临时改prompt后重试。字段依据：[固定Microsoft实现](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/index/operations/summarize_communities/community_reports_extractor.py#L25-L45)，2026-10-12静态核对。

## embedding金额怎么得到

OpenAI官方模型页在2026-10-12列出的普通输入价格为 **$0.13／百万token**，本计划不使用Batch折扣。因此20,000-token发送总额对应 **$0.0026税前模型输入费上限**，不是账户级消费上限，也不包含税费或别的进程调用。执行前若单价改变，应重新核对并停止使用旧金额。[官方价格](https://developers.openai.com/api/docs/models/text-embedding-3-large)是动态文档，未标文章发布日期，本次访问日2026-10-12。

`text-embedding-3-large`默认3072维、单段最大8192token；第三代embedding用 `cl100k_base`计数。本计划单段限8000，留有余量。[官方embedding指南](https://developers.openai.com/api/docs/guides/embeddings)，动态文档，访问2026-10-12。当前公开模型页只给出同名alias，不能伪称已锁定不可变模型snapshot；未来保存响应model与日期以说明此限制。

本机实测8块源码为4,247 token，4条dev为80 token，合计 **4,327**；剩余 **15,673** 留给可选图产物。结果、逐项计数和词表hash在[embedding-estimate.json](embedding-estimate.json)。这些是源码文本本地计数，不是服务已确认的账单。发送前预留全部输入额度；HTTP超时或响应不明也不退回额度，不重发。若实际usage与本地计数不符，立即停止后续请求并保留差异。

按用户选择，**不再估算one.fullstar金额**。仍记录每次请求的input/output usage、可见文本计数、耗时和失败原因；第三方模型映射、计费tokenizer及隐藏推理token语义未经验证，不能将共同计数当第三方费用承诺。

## 已准备什么，执行前还缺什么

[无密钥选定模板](ms-settings.selected.yaml)保留第三方endpoint占位符。Microsoft固定源码会把 `call_args` 合入LiteLLM参数，后续调用kwargs又可覆盖它；因此模板中的2048、timeout、`num_retries: 0`和 `drop_params: false`是候选参数，**尚不是经过验证的发送层限额**。[固定completion适配器](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-llm/graphrag_llm/completion/lite_llm_completion.py#L232-L261)，2026-10-12静态核对。embedding同样准备维度3072、30秒、0重试；接口尚未验证。

该YAML仍列出完整Standard工作流，**不能把直接执行它当作本表的8块探测**。本轮仅完成本地计数、配置语法与静态字段检查。完整传输适配器、请求前额度预留、所有层重试关闭、进程总超时／RSS监督及响应验证尚未接通；不能声称这些限额已在实际服务生效。

获准执行后应先把这些限制接到实际发送点并做离线拒绝测试，再发第一条真实请求；每次发送须验证最终合并参数，没有自动repair或fallback。第三方endpoint必须核实，不能凭域名猜路径。若服务拒绝输出限制或schema、静默忽略参数、返回模型不符、身份验证失败、429、超时、无usage或预算将超限，**停止本次探测**，保留已消耗额度与失败证据；不能自动重启一轮。由于第三方兼容性未知，请求的token上限只有服务正确执行时才是远端上限，本地停止无法撤回已经产生的远端计算。

密钥由用户手动放置，见[凭据说明](credentials.md)。用户设置后的受托检查仅确认存在、权限与两个指定变量非空，没有输出密钥或加载至客户端；CI不加载它。这里只提交placeholder。后续日志只保留脱敏请求ID、模型名、公开输入ID/hash、计数与耗时，不记录Authorization、解析后的配置或原始异常请求头。

这次批准范围不含114块完整索引、test集检索评分、feature改码、服务订阅、凭据授权变更或新模型下载。探测通过后再根据实际usage和缺失能力制定完整实验预算。

## 无模型调用的复核命令

已准备语料时先检查原冻结包，再重算embedding文本量：

```bash
python3 research/pilot/verify.py --source
.venv/bin/python research/pilot/measure_embedding.py
python3 research/pilot/verify_selection.py
```

复现时使用已安装 `research/pilot/requirements.txt` 的Python3.12环境即可，环境目录名可以替换。计数脚本拒绝缺失或hash不符的词表，不暗中下载。首次可单独获取公开词表：

```bash
TIKTOKEN_CACHE_DIR=.cache/pilot/tokenizer .venv/bin/python -c 'import tiktoken; tiktoken.get_encoding("cl100k_base")'
```

这只下载公开小词表，不调用embedding服务、不需要key。本轮准备阶段在Mac mini完成该下载与计数，没有使用本机或云浏览器。网页证据用只读网页工具核实；没有安装微软依赖或启动模型服务。
