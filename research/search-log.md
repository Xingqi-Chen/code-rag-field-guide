# 直接代码证据检索记录

检索执行日与研究截止：**2026-10-12（UTC）**。对象是 `microsoft/graphrag` 对代码索引与上下文检索的直接评测。初轮围绕代码理解、跨文件流程与架构，补检按用户聚焦细化为精确函数/符号定位、真实调用/依赖链、修改影响分析、辅助实现 feature（检索与生成分开）。本记录是可追踪的定向检索，不声称完整覆盖所有论文、公司内部实验或搜索引擎未收录资料。

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

### E. 四类代码索引与检索任务补检

以下为 2026-10-12 用户明确四类目标后实际执行的新增检索；无引号项按自然语言搜索。

```text
"Microsoft GraphRAG" "symbol" code retrieval
"microsoft/graphrag" "call graph"
"Microsoft GraphRAG" "impact analysis"
"Microsoft GraphRAG" "feature" code retrieval benchmark
"Microsoft GraphRAG" "code search"
"Microsoft GraphRAG" "code retrieval"
"GraphRAG" "symbol resolution"
"GraphRAG" "change impact" code evaluation
Microsoft GraphRAG function localization code benchmark
Microsoft GraphRAG call dependency chain source code evaluation
GraphRAG Microsoft change impact analysis repository benchmark
GraphRAG Microsoft repository feature implementation retrieval evaluation
"GraphRAG" "code porting" Microsoft
"GraphRAG" "function localization"
"GraphRAG" "feature location"
"microsoft/graphrag" "Recall" code
"MS-GraphRAG" "code" retrieval
"GraphRAG" "RepoQA" Microsoft
"GraphRAG" "code4llm" benchmark evaluation
```

新命中中，Julia 论坛的代码迁移讨论提供了有价值的 code4llm 线索；它没有直接给出受控分数。另有 clangd-graph-rag 等独立代码图项目，以及把生物学 gene symbol、Microsoft 产品泛用 GraphRAG 示例、GraphRAG 项目自身源代码/API 使用方式误匹配为代码检索的结果，均不按任务词表面匹配纳入。检索 Recall/RepoQA 也命中了工具汇编页中的并列链接，不代表这些基准测试过微软 GraphRAG。

### F. code4llm 官方研究与公开复现追查

```text
"Mark Russinovich" "GraphRAG"
"Microsoft is Getting Rusty" slides graphrag
"1VgptLwP588" GraphRAG
"code4llm" GraphRAG
"Microsoft is Getting Rusty" "GraphRAG" code4llm
"Mark Russinovich" "GraphRAG" "code" slides
"code4llm" microsoft
"Rust Nation" "GraphRAG" code
"Mark Russinovich" "GraphRAG" "Python"
code4llm Microsoft Russinovich code GraphRAG demo
"code4llm" "graph"
"Microsoft is Getting Rusty" "slides"
"code4llm" "Microsoft" -site:linkedin.com
"GraphRAG" "Rust" "Mark" "demo"
```

从 Julia 论坛到微软官方 issue #1779，再到关联 #1442，确认维护者本人称有代码相关 GraphRAG 研究。原始演讲 YouTube 页面未返回可读字幕，带时间戳 URL 读取失败；没有以论坛或 Reddit/HN 的转述替代原视频内容核验。搜索中的 SJTU `Code4LLM` 个人研究方向与此 demo 没有已核实关系，不按同名合并。本轮未定位到足以复核该微软研究的公开实现、任务集或结果表；这不表示它从未公开或今后不会公开。

## 3. 一手材料核验台账

| 材料 | 本轮读取范围 | 日期/版本锚点 | 判定 |
|---|---|---|---|
| [code4llm 公开请求 #1779](https://github.com/microsoft/graphrag/issues/1779) | issue 原文、请求者演讲链接、维护者回复与关闭状态 | opened 2025-03-03；`natoverse` 回复/关闭 2025-11-18；访问 2026-10-12 | 官方确认有代码相关 GraphRAG 研究，但没有公开实现版本、题集、检索指标或成本；不等同公开版包的评测 |
| [生成代码项目图请求 #1442](https://github.com/microsoft/graphrag/issues/1442) | 需求正文与维护者关联 #1779 | opened 2024-11-26；维护者回复 2025-11-18 | 功能请求与同一研究线索，不是另一项实验 |
| [GraphRAG for LLM-Based Code Porting](https://discourse.julialang.org/t/graphrag-for-llm-based-code-porting/134364) | 原帖、视频链接及微软 GitHub 跳转 | 2025-12-04 22:21；访问 2026-10-12 | 导航线索；用户的演示比较描述不能当原始评测 |
| [Microsoft is Getting Rusty 原视频](https://www.youtube.com/watch?v=1VgptLwP588) | 页面与带时间戳入口尝试；**没有读到字幕或完整演示内容** | Rust Nation UK 2025；精确视频发布日期本轮未核验 | 保留原始入口，不能声称独立看过或复核了演示 |
| [Mark Russinovich 本人演讲分享](https://www.linkedin.com/posts/markrussinovich_microsoft-is-getting-rusty-a-review-of-successes-activity-7300640259753553920-q2H5) | 作者称其 Rust Nation UK closing keynote 已上线 | 页面使用相对日期，不据此定精确日期 | 可确认演讲身份；评论中的迁移语言描述不当作者研究结果 |
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
| [clangd-graph-rag](https://github.com/2015xli/clangd-graph-rag) | README 方法与任务；requirements 静态读取 | 访问 2026-10-12，master 未锁 commit | Clang/clangd + Neo4j + Google ADK 自有方案；不能当微软调用链/feature 实测 |

固定源码关键位置：模型声明约 L33–34；结构化字段 L53–58；自定义提取 prompt L68–89；NetworkX 图 L91 起；批次 L106；截断 L126；成功映射 L169；依赖边 L174；`class_to_path.items()` 驱动入库 L239；top-k L282；前驱/后继 L302–303。以链接中的固定内容为准，网页显示行号可能不同。

## 4. 重要排除理由与候选保留

| 命中 | 处理与理由 |
|---|---|
| 微软原论文、官方 benchmarking、GraphRAG-Bench | 保留为非代码背景；不能把多文档主题推理结果改写为跨文件调用流程准确性 |
| code4llm 与 #1442 | **保留官方研究线索**；研究存在已确认，公开版实现身份和四类任务测量未确认；不按“无人研究”排除，也不把请求者体验当分数 |
| Reliable Graph-RAG for Codebases | 有代码 QA，但固定实现不是微软；保留身份核验及公平性问题，不迁移其成绩 |
| CodeRAG / GraphCodeAgent | 版本去重，明确 GraphCoder 与 GraphRAG 不同 |
| RepoCoder 引用的微软 `CodeT`、GraphCodeBERT、RepoGraph 等 | 机构或 graph 字样不能确认 `microsoft/graphrag` 身份 |
| [2389.ai RAG experiment](https://2389.ai/research/writing/experimenting-with-rag/)（2025-03-06） | 已读为行政命令语料、自定义 original/Lazy 混合；不是代码评测 |
| [2-million-token benchmark](https://dev.to/vedantdhavan/graphrag-benchmark-a-2-million-token-comparison-of-llm-only-basic-rag-and-graphrag-16ph)（页面日期2026-05-16） | 科学论文语料、自定义图方案；不作为微软代码效果来源 |
| [Consumer Hardware / EHR Schema Retrieval，2605.20815](https://arxiv.org/abs/2605.20815) | 只核摘要与任务范围；EHR schema 检索不是代码库理解，未作深入实现核查 |
| [BioHarness，2606.19396v1](https://arxiv.org/html/2606.19396v1)（2026-06-17） | gene symbol 是生物学符号；生物医学问答与代码执行辅助证据组装，不是程序符号定位或代码库 feature 检索 |
| [微软 issue #2121](https://github.com/microsoft/graphrag/issues/2121)（2025-11-06） | 询问如何在自己的 Python 源码 import GraphRAG；“source code” 指调用 API 的代码，不是被索引的源代码语料 |
| 泛 GraphRAG-Bench、WildGraphBench、技术文档图检索、FalkorDB/CodeGraph 产品页 | 无直接代码库微软实现评测身份，未用于效果结论 |
| [IEEE 11688270](https://ieeexplore.ieee.org/abstract/document/11688270/) | **保留未核实**：网页/PDF 读取失败；不因标题含 GraphRAG 就纳入，也不宣称确定不属于微软 |
| *From Code to Execution: Multi-Agent GraphRAG for Automated Artifact Generation* | 仅二级索引题名线索；精确题名检索未定位一手全文或实现。不能作效果来源 |

## 5. 访问限制与结论边界

- IEEE 候选的[PDF](https://ieeexplore.ieee.org/iel8/11688156/11688194/11688270.pdf)及摘要读取返回错误，无法审计身份、题集和指标。没有付费绕过。
- code4llm 原视频的网页读取没有可读字幕，时间戳入口失败；本轮没有亲自核验演示输入输出、迁移语言、计分或对照配置。维护者 2025-11-18 的回复是一手证据，但“当时没有开源计划”不能延伸成截止日永久不开放的承诺。
- 官方 benchmarking 仓库 `data/` 子目录网页读取失败；README 与对应论文可读，足以核实公开说明的语料范围，未声称逐个压缩包审计。
- Shell 对 GitHub API 的只读请求遇到 DNS/网络限制；随后使用公开网页与 raw 内容完成关键静态核验，没有执行外部脚本。没有尝试读取凭据或改动网络设置。
- CodeRAG-Bench v3 HTML URL 返回失败，改用可读 v2 和 ACL 入口。所有正文结论均注明已读版本。
- CodeRAG/GraphCodeAgent 论文提供的 Figshare 复现链接只记录入口，未下载验证；CodexGraph 的作者代码链接也不视为本轮已运行或完整审计。
- 若干带 `site:` 或严密引号的查询仍返回泛主题结果；对 `RepoQA`、`CodeQA` 等关键词的空命中不代表文献不存在。没有以搜索引擎返回数量作统计。
- 日期明确晚于研究截止的材料不纳入；未核实绝对日期的帖子仅作使用线索，不承担时间趋势或效果论证。

四类任务的补检结果：精确定位、调用/依赖链、修改影响和 feature 辅助均未获得可归属微软公开实现且可复核的量化成绩。对 feature 还需区分检索上下文质量与生成成功率；code4llm 研究存在得到官方确认，但不能填补上述两层分数。初轮已核验的 CodeRAG/GraphCodeAgent、CodexGraph、CodeRAG-Bench 与 Java 图问答论文重审后仍因实现身份不符或没有微软 baseline 而不能填补缺口。

最终措辞必须是：**“截至2026-10-12，在本轮公开检索范围内，未检索到足够直接证据。”** 同时明确 **“微软维护者确认有代码相关 GraphRAG 研究”**。不能缩写成“微软 GraphRAG 没人用于代码”“没有任何研究”“已证明它不适合代码”或“已有代码图实验证明微软有效”。

## 6. 代码索引基线与官方接口的补充阅读

2026-10-12 直接读取微软 GraphRAG 的 [outputs](https://microsoft.github.io/graphrag/index/outputs/)、[自有图接入](https://microsoft.github.io/graphrag/index/byog/)和 [CLI](https://microsoft.github.io/graphrag/cli/)说明；实现结论仍以 v3.3.0 固定源码为准。尝试的 `/index/update/` 页面读取失败，没有以不存在的文档段落作证据。

为解释传统语言工具为何是相关基线，读取官方 LSP 3.17 的 [definition.md](https://raw.githubusercontent.com/microsoft/language-server-protocol/gh-pages/_specifications/lsp/3.17/language/definition.md)和 [callHierarchy.md](https://raw.githubusercontent.com/microsoft/language-server-protocol/gh-pages/_specifications/lsp/3.17/language/callHierarchy.md)。公开规范 HTML 在本次工具中仅返回目录，改读同一官方仓库的规范正文。版本是目录标注的 3.17，链接位于可变的 gh-pages 分支，未锁 commit，访问日为上述日期。仅据此说明协议中的定义位置、URI/range、进入／发出调用和能力声明，不声称具体语言服务器已实现，也不将协议当成语义正确性证明。这些不是微软 GraphRAG 效果证据。
