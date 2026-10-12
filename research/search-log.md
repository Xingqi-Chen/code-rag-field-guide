# 直接代码证据检索记录

检索执行日与研究截止：**2026-10-12（UTC）**。对象是 `microsoft/graphrag` 对代码理解、跨文件流程、架构理解的直接评测。本记录是可追踪的定向检索，不声称完整覆盖所有论文、公司内部实验或搜索引擎未收录资料。

## 1. 来源与操作范围

使用公开联网检索，优先读取 arXiv/ACL/IEEE 原文、微软官方资料、作者 GitHub 和固定源码。使用者反馈仅取其本人帖子或评论，并明确降为经验陈述。没有把第三方新闻、营销文案、星标数、机构名声作为效果证据。

核查步骤为：题名检索 → 正文任务/语料 → 基线列表 → Microsoft/GraphRAG/Edge 引用身份 → 作者代码与版本 → 对照公平性及指标 → 成本与复现范围。全文搜索没有命中不是唯一排除依据；重点论文还读取了方法、实验和 baseline 部分。

公开源码只做静态阅读。本轮没有执行下载项目的脚本、调用付费模型或复现实验；没有访问无关本地仓库或凭据。检索工作形成直接证据表和本记录。

## 2. 实际使用的检索式

以下均于 2026-10-12 执行；引号为检索时的原样限定。多次组合与追加检索用于确认可能被名称、领域或索引方式漏掉的工作，不据搜索命中数计算“文献数量”。

### A. 明确 Microsoft 身份与代码目标

```text
"Microsoft GraphRAG" code repository evaluation
"microsoft/graphrag" code question answering benchmark
"Microsoft GraphRAG" "codebase"
"microsoft/graphrag" "benchmark" "code"
"Microsoft GraphRAG" "codebase" evaluation
"Microsoft GraphRAG" "code" "evaluation" -site:medium.com -site:linkedin.com -site:reddit.com
"graphrag" "source code" "microsoft" benchmark
"graphrag" "repository understanding" "Microsoft"
"graphrag" "codebase" benchmark Microsoft
"microsoft/graphrag" "codebase"
"Microsoft GraphRAG" software
"MS-GraphRAG" code
"Microsoft GraphRAG" "Java"
"Microsoft GraphRAG" "Python" "evaluation"
```

### B. 去掉严格引号与中文补检

```text
graphrag code repository evaluation Microsoft benchmark
Microsoft GraphRAG source code understanding experiment
graphrag software architecture source code arxiv
Microsoft GraphRAG 代码库 评测
Microsoft GraphRAG codebase benchmark site:arxiv.org
Microsoft GraphRAG code analysis benchmark site:github.com
graphrag codebase  [domain filter: arxiv.org]
```

### C. 近名研究与任务词追查

```text
"CodeRAG" "GraphRAG" evaluation
"GraphCodeAgent" "GraphRAG" Microsoft
"CodeRAG" "GraphRAG"
"GraphCodeAgent"
"CodexGraph" "GraphRAG"
GraphCodeAgent arxiv
CodeRAG graph code retrieval augmented generation arxiv
CodexGraph arxiv
"Reliable Graph-RAG for Codebases"
"GraphRAG" "code comprehension"
"GraphRAG" "software architecture" evaluation
"GraphRAG" "code question answering"
"GraphRAG" "repository-level"
"GraphRAG" "codebase understanding"
"CodeRAG" Microsoft
"GraphRAG" "RepoQA"
"GraphRAG" "SWE-bench"
"GraphRAG" "CodeQA"
"GraphRAG" "DevEval"
"GraphRAG" "CodeRAG"
"From Code to Execution" "GraphRAG"
"Automated Artifact Generation" GraphRAG
"GraphRAG-Driven Self-Healing"
```

补充协作检索式：`"Microsoft GraphRAG" "codebase" evaluation`、`"microsoft/graphrag" "code" benchmark`、`"GraphRAG" "source code" "Microsoft" evaluation benchmark`。补充命中主要为 GraphRAG-Bench、官方 benchmarking 数据集及泛代码图项目；已独立读取前两者的一手资料核实领域。

### D. 代码实施案例补检

```text
site:github.com/microsoft/graphrag "codebase"
site:github.com/microsoft/graphrag "source code" "index"
"graphrag" "codebase" "requirements.txt"
"graphrag" "source code" "settings.yaml"
graphrag codebase Microsoft github discussions
Microsoft GraphRAG source code codebase github example
Microsoft graphrag index code repository example tutorial
"GraphRAG" "code base" Microsoft
"graphrag" "legacy code" github
```

同时尝试微软仓库 discussions/issues 的 `codebase` 查询 URL；页面读取失败。补检主要重新命中 #322，另命中 SAP 迁移论文与 Thoughtworks 实践文，均进一步读取原文核验。公开 Myrmion README 与 requirements 也已静态读取，确认是 LightRAG 加独立代码图，不计微软案例。

## 3. 一手材料核验台账

| 材料 | 本轮读取范围 | 日期/版本锚点 | 判定 |
|---|---|---|---|
| [From Local to Global](https://arxiv.org/html/2404.16130v2) | 方法、语料、评价、成本与局限 | v2，2025-02-19 | 微软原始证据，新闻/播客不是代码 |
| [微软官方 narrative-private-data 博文](https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/) | 案例领域 | 2024-02-13 | VIINA 新闻案例，不是源码 |
| [官方数据集 README](https://raw.githubusercontent.com/microsoft/graphrag-benchmarking-datasets/main/README.md) | 数据归属、论文链接与 CLI | 访问时 main，未锁 commit | 指向 open-domain QA 数据；README 明示 HotpotQA、Kevin Scott Podcasts |
| [Optimizing open-domain question answering…](https://arxiv.org/html/2503.02922v1) | §4 数据集与方法身份 | v1，2025-03-04；GraphRAG v0.3.6 | 另含 MSMARCO、财报；仍没有源代码库 |
| [GraphRAG-Bench](https://arxiv.org/html/2506.05690v3) | §3.2、结果方法名、附录 H、模型规模实验对象 | v3，2026-02-22 | 小说/医学；有 MS-GraphRAG，但不是代码领域 |
| [微软讨论 #322](https://github.com/microsoft/graphrag/discussions/322) | 找到 legacy codebase 评论并核日期 | `gona-sreelatha`，2025-10-13 | 正面使用自述，无受控评测 |
| [Graphrag but for code](https://www.reddit.com/r/LocalLLaMA/comments/1i62uwo/graphrag_but_for_code/) | 原作者试用与自建方案陈述 | 绝对发帖日未核验；访问2026-10-12 | 负面体验，无微软试用复现材料 |
| [Reliable Graph-RAG for Codebases](https://arxiv.org/html/2601.08773v1) | 方法、三项目评测、结果、成本、局限与代码链接 | v1，2026-01-13 | 任务符合，但 LLM-KB 不是微软实现 |
| [该文固定源码](https://raw.githubusercontent.com/Manideep-Reddy-Chinthareddy/graph-based-rag-ast-vs-llm/efa7c88ff998877d825b722a595b9f0201719da4/llmkb_gemini.py) | 导入、提取 prompt、Pydantic schema、图构建、入库和查询 | commit `efa7c88ff998877d825b722a595b9f0201719da4` | Gemini JSON → NetworkX → Chroma 与邻域扩展；无微软流水线 |
| [该文作者仓库](https://github.com/Manideep-Reddy-Chinthareddy/graph-based-rag-ast-vs-llm) | 目录与 main 源码，与固定提交对照 | main 为可变链接；结论优先固定提交 | 有源码、日志、成本等；未执行 |
| [CodeRAG 2504.10046v1](https://arxiv.org/html/2504.10046v1) / [GraphCodeAgent v2](https://arxiv.org/html/2504.10046v2) | 正文检索、方法、§4.2 baselines、数据与复现链接 | v1 2025-04-14；v2 2025-11-18 | 同一研究更新；基线无微软 GraphRAG |
| [CodeRAG 2509.16112v1](https://arxiv.org/html/2509.16112v1) | 方法与 baseline；[ACL入口](https://aclanthology.org/2025.emnlp-main.1187/)及[作者仓库](https://github.com/KDEGroup/CodeRAG) | v1，2025-09-19 | 另一同名研究，未测试微软 GraphRAG |
| [CodexGraph 2408.03910v2](https://arxiv.org/html/2408.03910v2) | 图来源、baseline、评测语料及演示类型 | v2 | 自己的代码图与 agent；没有微软 baseline |
| [CodeRAG-Bench 2406.14497v2](https://arxiv.org/html/2406.14497v2) | §3.1、表3、任务定义 | v2，2025-02-26 | 检索器基准，无微软 GraphRAG 实验 |
| [CGM 2505.16901v4](https://arxiv.org/html/2505.16901v4) | 方法、实验及 Microsoft/GraphRAG 字样定位 | v4，2025-06-23 | 自有图模型与 R3，不能认作微软 |
| [Prometheus 2507.19942v1](https://arxiv.org/html/2507.19942v1) | 方法和 §5.2 相关工作 | v1，2025-07-26 | GraphRAG 为泛领域引用；不是微软测试 |
| [Towards Practical GraphRAG 2507.03226v3](https://arxiv.org/html/2507.03226v3) | §3 方法、§4 数据/对照、相关工作；[公开示例 README](https://raw.githubusercontent.com/lingvisa/graphrag-pakdd2026-evaluation/personal/README.md) | v3，2025-12-18 | SAP 自有方法；550份迁移PDF而非代码库索引；没有微软基线 |
| [Legacy Modernization meets GenAI](https://martinfowler.com/articles/legacy-modernization-gen-ai.html) | CodeConcise 案例、微软 GraphRAG 提及语境 | 2024-09-24 | 微软方法是可能应用的设想，不是已验证流水线 |
| [Myrmion](https://github.com/e2its/myrmion-graphrag) | README 架构、requirements | 访问时 main，未锁 commit | LightRAG 文档端 + 自有代码解析图；不属微软 |

固定源码关键位置：模型声明约 L33–34；结构化字段 L53–58；自定义提取 prompt L68–89；NetworkX 图 L91 起；批次 L106；截断 L126；成功映射 L169；依赖边 L174；`class_to_path.items()` 驱动入库 L239；top-k L282；前驱/后继 L302–303。以链接中的固定内容为准，网页显示行号可能不同。

## 4. 重要排除理由与候选保留

| 命中 | 处理与理由 |
|---|---|
| 微软原论文、官方 benchmarking、GraphRAG-Bench | 保留为非代码背景；不能把多文档主题推理结果改写为跨文件调用流程准确性 |
| Reliable Graph-RAG for Codebases | 有代码 QA，但固定实现不是微软；保留身份核验及公平性问题，不迁移其成绩 |
| CodeRAG / GraphCodeAgent | 版本去重，明确 GraphCoder 与 GraphRAG 不同 |
| RepoCoder 引用的微软 `CodeT`、GraphCodeBERT、RepoGraph 等 | 机构或 graph 字样不能确认 `microsoft/graphrag` 身份 |
| [2389.ai RAG experiment](https://2389.ai/research/writing/experimenting-with-rag/)（2025-03-06） | 已读为行政命令语料、自定义 original/Lazy 混合；不是代码评测 |
| [2-million-token benchmark](https://dev.to/vedantdhavan/graphrag-benchmark-a-2-million-token-comparison-of-llm-only-basic-rag-and-graphrag-16ph)（页面日期2026-05-16） | 科学论文语料、自定义图方案；不作为微软代码效果来源 |
| [Consumer Hardware / EHR Schema Retrieval，2605.20815](https://arxiv.org/abs/2605.20815) | 只核摘要与任务范围；EHR schema 检索不是代码库理解，未作深入实现核查 |
| 泛 GraphRAG-Bench、WildGraphBench、技术文档图检索、FalkorDB/CodeGraph 产品页 | 无直接代码库微软实现评测身份，未用于效果结论 |
| [IEEE 11688270](https://ieeexplore.ieee.org/abstract/document/11688270/) | **保留未核实**：网页/PDF 读取失败；不因标题含 GraphRAG 就纳入，也不宣称确定不属于微软 |
| *From Code to Execution: Multi-Agent GraphRAG for Automated Artifact Generation* | 仅二级索引题名线索；精确题名检索未定位一手全文或实现。不能作效果来源 |

## 5. 访问限制与结论边界

- IEEE 候选的[PDF](https://ieeexplore.ieee.org/iel8/11688156/11688194/11688270.pdf)及摘要读取返回错误，无法审计身份、题集和指标。没有付费绕过。
- 官方 benchmarking 仓库 `data/` 子目录网页读取失败；README 与对应论文可读，足以核实公开说明的语料范围，未声称逐个压缩包审计。
- Shell 对 GitHub API 的只读请求遇到 DNS/网络限制；随后使用公开网页与 raw 内容完成关键静态核验，没有执行外部脚本。没有尝试读取凭据或改动网络设置。
- CodeRAG-Bench v3 HTML URL 返回失败，改用可读 v2 和 ACL 入口。所有正文结论均注明已读版本。
- CodeRAG/GraphCodeAgent 论文提供的 Figshare 复现链接只记录入口，未下载验证；CodexGraph 的作者代码链接也不视为本轮已运行或完整审计。
- 若干带 `site:` 或严密引号的查询仍返回泛主题结果；对 `RepoQA`、`CodeQA` 等关键词的空命中不代表文献不存在。没有以搜索引擎返回数量作统计。
- 日期明确晚于研究截止的材料不纳入；未核实绝对日期的帖子仅作使用线索，不承担时间趋势或效果论证。

最终措辞必须是：**“截至2026-10-12，在本轮公开检索范围内，未检索到足够直接证据。”** 不能缩写成“微软 GraphRAG 没人用于代码”“没有任何研究”“已证明它不适合代码”或“已有代码图实验证明微软有效”。
