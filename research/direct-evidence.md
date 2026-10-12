# Microsoft GraphRAG 用于代码理解：直接证据核查

研究截止与访问日：**2026-10-12（UTC）**。本文件只回答微软 GraphRAG 对代码问答、跨文件流程和整体架构理解的效果证据是否足够；检索范围与未解决项见[检索记录](search-log.md)。论文数字均为作者报告，本轮没有运行外部项目或付费模型，也没有把本仓库旧实验当作微软证据。

**结论：在本轮公开文献、作者代码和微软项目资料的检索范围内，未检索到足够直接证据，能够据此判断 Microsoft GraphRAG 在代码库理解上的准确性增益、成本收益或稳定适用条件。** 找到了直接使用的正反反馈，但缺少可核验版本与受控评测；找到了代码理解实验，但最接近的实验并未使用微软实现。这不等于“没人研究”，也不证明微软 GraphRAG 对代码无效。

现有证据支持做机制介绍、提出试点假设；**不支持免去目标代码库上的评测，直接宣称微软 GraphRAG 更好或更差**。若决定暂不做实验，合适的产出是“效果尚未验证”的技术评估，而不是性能结论。

## 1. 本次如何认定直接证据

证据必须同时满足两个条件：第一，实际实验对象可追溯到 [`microsoft/graphrag`](https://github.com/microsoft/graphrag)，或明确说明对该实现的版本与修改；第二，输入包含源代码库，任务直接测试代码理解、跨文件依赖或流程、架构解释。论文只引用 Edge 等人的原论文、名字含 GraphRAG、由微软发表，均不满足实现身份条件。图驱动代码补全或修复可以提供邻近证据，但也不能直接等价为架构问答的正确性。

一份足以支撑选型的实验还应交代：代码快照、语言与规模、题集及参考答案、检索和生成配置、公平对照、准确性与证据指标、失败情况、构建和查询成本、复现资料。缺字段记为未报告或未核实，不替作者补全。

## 2. 候选证据矩阵

| 候选与版本 | 微软实现身份 | 代码与任务 | 本轮核查结果 | 可承担的论证 |
|---|---|---|---|---|
| [From Local to Global，2404.16130v2](https://arxiv.org/html/2404.16130v2)，2025-02-19 | 原始微软 GraphRAG 方法研究 | 播客、新闻；全局主题归纳 | 官方实验证据，领域不是代码 | 解释方法设计与原有适用场景，不能推导代码正确率 |
| [Optimizing open-domain QA，2503.02922v1](https://arxiv.org/html/2503.02922v1)，2025-03-04；[官方数据仓库](https://github.com/microsoft/graphrag-benchmarking-datasets) | 明确 GraphRAG v0.3.6 | HotpotQA、MSMARCO、财报电话会、播客 | 身份清晰，但没有代码库任务 | 非代码领域的比较；不是代码评测补缺 |
| [GraphRAG-Bench，2506.05690v3](https://arxiv.org/html/2506.05690v3)，2026-02-22 | 正文明确 MS-GraphRAG local/global；本轮未进一步审计其依赖锁定与补丁 | Gutenberg 小说、NCCN 医学指南 | 不是源代码语料 | 可讨论跨领域适用性限制，不能迁移为代码结论 |
| [微软仓库讨论 #322](https://github.com/microsoft/graphrag/discussions/322)，2025-10-13 用户评论 | 微软项目讨论区内的使用自述；具体实现和改动未核实 | 遗留代码探索、需求提取、依赖映射、迁移 | 正面经验，没有题集、对照、指标或复现产物 | 证明存在公开使用反馈；不能证明效果 |
| [“Graphrag but for code”原作者帖子](https://www.reddit.com/r/LocalLLaMA/comments/1i62uwo/graphrag_but_for_code/)，绝对发帖日未核验 | 用户明确自述尝试 Microsoft GraphRAG；版本未核实 | 大型代码库理解，随后自行做代码结构图 | 负面体验，没有可复核评测 | 证明存在试用与改造需求；不能估计普遍失败率 |
| [Reliable Graph-RAG for Codebases，2601.08773v1](https://arxiv.org/html/2601.08773v1)，2026-01-13 | **已核验不是微软实现**：作者自定义 LLM 依赖图与邻域扩展 | 三个 Java 项目、45 个架构/代码追踪问题 | 最接近所问任务，但实验身份不符 | 邻近方法的实验设计和风险线索，不能给微软方法贴成绩 |
| [CodeRAG，2504.10046v1](https://arxiv.org/html/2504.10046v1)，2025-04-14 → [GraphCodeAgent，v2](https://arxiv.org/html/2504.10046v2)，2025-11-18 | 两版本已读正文与基线表未出现微软 GraphRAG | 仓库级代码生成；双图与 agent 检索 | **同一 arXiv 记录的两个版本，不能算两项独立实验** | 不能作为 Microsoft GraphRAG baseline 的证据 |
| [另一篇 CodeRAG，2509.16112v1](https://arxiv.org/html/2509.16112v1)，2025-09-19 | 已读基线无微软 GraphRAG | 仓库级代码补全；多路检索与重排 | 同名不同论文；RG-1 不是 MS-GraphRAG | 排除名称混淆 |
| [CodexGraph，2408.03910v2](https://arxiv.org/html/2408.03910v2) | 静态代码图与图查询 agent；已读对照无微软 GraphRAG | 代码补全、问题修复，另有 Code Chat 演示 | 不能替代微软在代码上的对照评测 | 仅用于说明另有代码结构方法，不用于证明微软效果 |
| [CodeRAG-Bench，2406.14497v2](https://arxiv.org/html/2406.14497v2)，2025-02-26 | §3.1/表3 为稀疏与稠密检索器，无微软 GraphRAG | 代码生成与检索基准 | 基准相关，但未运行所需对象 | 可供未来选题，不是既有微软结果 |
| [Towards Practical GraphRAG，2507.03226v3](https://arxiv.org/html/2507.03226v3)，2025-12-18 | 论文描述作者自己的图检索；没有微软基线 | SAP ABAP 迁移问答与代码生成；索引迁移文档 | 有实测，但既非微软实现评测，也非代码库结构检索 | 不能把其迁移收益归给微软 GraphRAG |
| [GraphRAG-Driven Self-Healing Multi-Agent Framework…，IEEE 11688270](https://ieeexplore.ieee.org/abstract/document/11688270/) | **未核实** | 搜索摘要称软件修复评测 | 正文/PDF 访问失败，未找到可审计作者实现 | 待核验候选；不计入支持或否定证据 |

上表的“未出现”只针对本轮所读论文版本的实验设置与基线，不是对整个研究团队或未来版本的断言。

## 3. 确实涉及微软的材料，为什么仍不足以回答代码问题

### 官方原始实验的适用边界

[原论文 v2](https://arxiv.org/html/2404.16130v2)的两个语料约为 100 万 token 播客与 170 万 token 新闻。比较对象包括向量检索、全文分块 map-reduce、不同社区层级 GraphRAG；主要指标是 LLM 对完整性、多样性等的成对偏好，不是可执行代码正确性或调用链准确率。论文报告的偏好胜率不能改写为“代码回答准确率”。单次生成上下文预算相同，也不表示整条流水线总计算预算相同。

同一论文中常被引用的“减少 9–43 倍 token”是相对全文源文本 map-reduce 对照，不能写成“比向量 RAG 普遍便宜 9–43 倍”。论文明确只测试两个语料，尚需研究泛化，且该评测没有衡量虚构信息率。这些限制与是否由微软发表无关。

[官方 benchmarking 数据仓库 README](https://raw.githubusercontent.com/microsoft/graphrag-benchmarking-datasets/main/README.md)链接的是上述 open-domain QA 研究，并提供 GraphRAG CLI 用法。该[论文 §4](https://arxiv.org/html/2503.02922v1)明确版本 v0.3.6：Global 社区层级 4、Local 层级 5；Local 上下文分配为文本 50%、摘要 10%、实体/关系 40%。它比较多个 RAG 方法，但语料仍为一般问答、财报和播客。版本明确增强了可追溯性，不会改变领域不匹配的问题。

[GraphRAG-Bench v3 §3.2、附录 H](https://arxiv.org/html/2506.05690v3)提供小说与医学文本上的 MS-GraphRAG 比较，作者[代码仓库](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark)可进一步追踪。它没有提供源代码调用链或软件架构题集。也不能把该文以 HippoRAG2 为代表的模型大小、语料规模实验归到微软 GraphRAG 名下。

### 公开代码使用反馈的缺口

| 应核验字段 | 微软讨论区正面反馈 | 原作者帖子负面反馈 |
|---|---|---|
| 版本、commit、原生/改造实现 | 未报告 | 未报告 |
| 编程语言、文件数、token、代码快照 | 未报告 | 原微软试用语料未报告；后续自建工具支持 Java，不能倒推原语料语言 |
| 问题集合与参考答案 | 未报告 | 未报告 |
| 向量/BM25/长上下文等对照 | 未报告 | 未报告 |
| 准确性、证据、跨文件流程或架构评分 | 未报告 | 未报告 |
| 模型、预算、公平性、构建/查询成本 | 未报告 | 未报告 |
| 可执行复现材料 | 未提供该微软试用的复现材料 | 未提供该微软试用的复现材料 |

2025-10-13，用户 `gona-sreelatha` 在[微软讨论区](https://github.com/microsoft/graphrag/discussions/322)称其用于遗留代码探索、依赖映射和迁移并有良好体验。这是用户反馈，不是微软背书或测量结果。另一位开发者在[自己的帖子](https://www.reddit.com/r/LocalLLaMA/comments/1i62uwo/graphrag_but_for_code/)称曾尝试微软 GraphRAG，认为其较重、不易扩展且未充分利用代码结构，随后开发自己的代码图方案。两者可以并列保留，不能据此投票得出效果结论。

## 4. 最容易误算为微软证据的 Java 论文

[Reliable Graph-RAG for Codebases](https://arxiv.org/html/2601.08773v1)有最接近需求的任务：Shopizer、ThingsBoard、OpenMRS Core 三个 Java 项目，分别 1,210、4,521、1,258 个文件，每个项目 15 个问题。作者比较 NoGraph、LLM-KB、AST-DKB。它引用微软原论文，但“引用”不是“运行微软实现”。

已静态读取论文指向的[固定提交 `efa7c88ff998877d825b722a595b9f0201719da4` 中 `llmkb_gemini.py`](https://github.com/Manideep-Reddy-Chinthareddy/graph-based-rag-ast-vs-llm/blob/efa7c88ff998877d825b722a595b9f0201719da4/llmkb_gemini.py)（[raw](https://raw.githubusercontent.com/Manideep-Reddy-Chinthareddy/graph-based-rag-ast-vs-llm/efa7c88ff998877d825b722a595b9f0201719da4/llmkb_gemini.py)）。实现身份如下：

- LangChain 调用 `gemini-3-flash-preview`，要求返回 `file_path / class_name / dependencies` JSON；NetworkX 创建依赖图。
- Chroma 向量检索 top-10 后，读取节点前驱与后继补充文件源代码。
- 没有导入微软 `graphrag`，没有其社区报告或 Global map-reduce 查询流水线；不是对微软代码库的包装。
- 每批 10 个文件、每文件取前 15,000 字符做 LLM 图提取；向量库从成功映射的 `class_to_path` 生成。图提取覆盖会影响后续可检索源文件集合，而不是只影响“有没有图”。

因此可以将它称为“作者的 LLM 抽取图与 AST 图比较”，不能称为“微软 GraphRAG 与 AST 比较”。

为防止数字被错用，保留其最小结果与边界：[论文表格](https://arxiv.org/html/2601.08773v1)中三个项目的 **Correct** 数分别为 NoGraph `6/14/11`、LLM-KB `13/12/13`、DKB `15/14/14`，各分母均为 15；Shopizer 建索引加 15 次问答的报告成本为 `$0.04 / $0.79 / $0.09`。这些是作者方法的结果，**不是微软 GraphRAG 的分数或报价**。评价为人工 Correct/Partial/Incorrect，题量小；未给出评审者一致性、置信区间与明确重复次数。

即使评估该作者方法，也要注意公平性：相同模型、chunk 大小、top-k 并不自动保证相同候选语料和最终上下文。上面的源代码表明 LLM 抽取成功与否会改变入库文件集合；不能把覆盖不足完全归因于“LLM 图天然不适合代码”。[作者仓库](https://github.com/Manideep-Reddy-Chinthareddy/graph-based-rag-ast-vs-llm)提供脚本、日志等材料；本轮只核验来源和静态代码，未独立复现其结果。

## 5. 名称近似的重点排除项

- **CodeRAG / GraphCodeAgent（2504.10046）**：v1 与 v2 为同一论文记录。v2 §4.2 基线包括 ScratchCG、BM25、Dense RACG、RepoCoder、GraphCoder、CodeAgent；其中 **GraphCoder 不是 GraphRAG**。其双图用于 DevEval、CoderEval 代码生成，不能补上微软方法的实测空白。[v1](https://arxiv.org/html/2504.10046v1)、[v2](https://arxiv.org/html/2504.10046v2)、[论文所列复现材料](https://figshare.com/s/4148a1c56d08804cd75a)；最后一个链接本轮未下载验证。
- **CodeRAG（2509.16112）**：是另一团队的同名工作。已读正文比较 CCFinder、RG-1、RepoCoder、DraCo、RepoFuse、Repoformer 等；其多路检索与 BestFit 重排不是微软 GraphRAG。名称中的 `RG-1` 也不能据字面归类为 GraphRAG。[论文](https://arxiv.org/html/2509.16112v1)、[作者代码](https://github.com/KDEGroup/CodeRAG)。
- **CodexGraph**：静态结构图、自然语言到图查询以及工具循环构成自己的方法；已读主要对照为 NoRAG、BM25、AutoCodeRover。代码对话演示不等于 Microsoft GraphRAG 的架构问答受控评测。[论文](https://arxiv.org/html/2408.03910v2)、[论文所列代码入口](https://github.com/modelscope/modelscope-agent/tree/master/apps/codexgraph_agent)。
- **CodeRAG-Bench**：基准含代码任务，但已读实验比较 BM25、通用/代码向量检索器和重排器，没有微软 GraphRAG baseline。[论文 §3.1/表3](https://arxiv.org/html/2406.14497v2)、[项目](https://code-rag-bench.github.io/)。
- **Code Graph Model（CGM）与 Prometheus**：文中出现 Graph RAG/GraphRAG 术语，不代表调用微软实现；前者是图整合模型与 R3，后者是多语言代码知识图与 agent 工作流。本轮未找到它们对 Microsoft GraphRAG 的直接评测。[CGM v4](https://arxiv.org/html/2505.16901v4)、[Prometheus v1](https://arxiv.org/html/2507.19942v1)。
- **SAP 的 Towards Practical GraphRAG**：§3 描述 SpaCy/GPT 三元组提取、igraph/Milvus、单跳邻域和 RRF；§4 对照是 dense vector，没有微软方法。其知识库为 550 份迁移 PDF，题集为 150 个迁移问答及 200 个 ABAP 迁移样例。不能把“代码迁移任务”误写成“直接索引代码库”，也不能把文中的 GraphRAG 分数归到微软实现。[论文 v3](https://arxiv.org/html/2507.03226v3)、[公开评测示例仓库](https://github.com/lingvisa/graphrag-pakdd2026-evaluation)。
- **Thoughtworks CodeConcise 实践文**：文中对微软 GraphRAG 的说法是“可能用于”抽取文档知识；已报告的 COBOL 案例是 CodeConcise 自有代码图与生成解释。该文不证明案例实际执行了微软流水线。[作者实践文章，2024-09-24](https://martinfowler.com/articles/legacy-modernization-gen-ai.html)。

这些排除项仅用于核对证据身份，本报告不据此扩写泛图 RAG 综述。GraphCodeBERT、RepoGraph、CodeQL、CodeGraph 等名字也不能因出现 graph 或 Microsoft 归为 `microsoft/graphrag`。

补充对微软 issues/discussions、公开依赖文件和实施示例的定向检索，未新增可核验微软版本、源代码输入与输出的代码理解演示。现有两个使用自述仍应标为“实施反馈，不能证明增益”，不凑成实验数量。例如命中的 [Myrmion](https://github.com/e2its/myrmion-graphrag) README 明确文档端是 LightRAG、代码端是自有解析图，并非微软 GraphRAG。

## 6. 尚未核实与下一步判断

[IEEE 11688270](https://ieeexplore.ieee.org/abstract/document/11688270/) 的搜索摘要涉及 GraphRAG 和软件修复，但正文与 [PDF](https://ieeexplore.ieee.org/iel8/11688156/11688194/11688270.pdf)访问失败，未核验实现身份、版本、对照及发表确切日期。其状态是“证据待核实”，不能把它肯定或否定为微软实测。搜索还出现未定位到一手全文的题名 *From Code to Execution: Multi-Agent GraphRAG for Automated Artifact Generation*，仅作后续线索。

因此，对四类目标——局部代码问答、跨文件流程、整体架构概览、变更影响——本轮都没有获得足以替代目标仓库评测的微软专属效果证据。可检验的假设包括：社区摘要是否改善架构归纳；LLM 提取关系是否忠实于代码；全局检索是否遗漏关键条件和调用方向；构建成本是否能由重复查询摊薄。这些属于**机制驱动的待测问题**，不是本文已证明的优缺点。

若后续加入 AST/调用图适配层，应分别评估“原生微软 GraphRAG”和“代码结构适配后的微软 GraphRAG”，明确版本、输入序列化、提示词与查询路径。否则即使得到好结果，也无法回答收益来自微软流水线、结构化输入，还是额外工具。
