# 来源与证据边界

与 [报告](report.md) 配套。研究截止和所有条目的访问日均为 **2026-10-12**。下面的版本日期与访问日期不同：前者说明材料何时发表／修订，后者说明本次核查时间。论文尽量链接固定 arXiv 版本；持续更新的文档没有稳定版本号时如实记录，不把网页版权年份当发布日期。

本报告只把一手论文、作者仓库和官方文档用于事实依据。二手综述及搜索摘要仅帮助发现线索，找到原文后再核查。本文不是系统性文献综述；研究日之后的材料不在范围内。

## 论文

| ID | 一手来源与 URL | 首发／本次采用版本 | 能支持什么 | 证据边界 |
| --- | --- | --- | --- | --- |
| S1 | Edge et al., [From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://arxiv.org/abs/2404.16130v2)；[全文](https://arxiv.org/html/2404.16130v2) | 首发 2024-04-24；v2 2025-02-19 | 文档实体图、社区摘要及全局归纳问答的设计与作者实验 | 两个文本集合、LLM 评判；不直接验证代码定位／修复，也未充分评错误陈述率；不是代码强 hybrid＋reranker 对照 |
| S4 | Guo et al., [GraphCodeBERT: Pre-training Code Representations with Data Flow](https://arxiv.org/abs/2009.08366v4) | 首发 2020-09-17；v4 2021-09-13；页面标注 ICLR 2021 | 数据流用于代码表示预训练与注意力 | 不属于在线仓库图遍历；不能作为 GraphRAG 产品比较 |
| S5 | Zhang et al., [RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation](https://arxiv.org/abs/2303.12570v3) | 首发 2023-03-22；v3 2023-10-20；EMNLP 2023 | 相似检索与生成迭代、RepoEval 补全实验 | 非图方法；补全场景不能直接等同真实 issue 修复 |
| S6 | Ouyang et al., [RepoGraph](https://arxiv.org/abs/2410.14684v2)；[方法与实验全文](https://arxiv.org/html/2410.14684v2) | 首发 2024-10-03；v2 2025-03-18；ICLR 2025 | 定义／引用、包含／调用关系及插入已有工程框架的作者实验 | 组合系统结果，不能将全部提升归于某一条边；本文未复现完整流水线 |
| S7 | Chen et al., [LocAgent: Graph-Guided LLM Agents for Code Localization](https://arxiv.org/abs/2503.09089v2)；[全文](https://arxiv.org/html/2503.09089v2) | 首发 2025-03-12；v2 2025-04-29 | Python 异构代码图、稀疏实体索引、agent 搜索／遍历工具 | 文件／函数／行定位指标不同；最高成绩、微调收益和成本降幅都有模型与设置前提，不能独立归因图 |
| S8 | Wang et al., [CodeRAG-Bench: Can Retrieval Augment Code Generation?](https://arxiv.org/abs/2406.14497v2)；[全文](https://arxiv.org/html/2406.14497v2) | 首发 2024-06-20；v2 2025-02-26 | 多来源、多任务、不同检索器与生成器比较 | 基准内的相对表现；不是所有代码检索器或商业产品的横向测评；不能把提供 gold 的实验当真实检索水平 |
| S9 | Liu et al., [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172v3) | 首发 2023-07-06；v3 2023-11-20 | 当时模型在文档问答／键值任务上的位置敏感性 | 非 2026 代码 agent 评测，不能用旧模型结果否定所有长上下文方案 |
| S20 | Wu et al., [Repoformer: Selective Retrieval for Repository-Level Code Completion](https://arxiv.org/abs/2403.10059v2) | 首发 2024-03-15；v2 2024-06-04；ICML 2024 | 学习何时检索，研究不必要／有害上下文 | 训练过的选择策略与特定补全设置；不是图消融 |
| S21 | Wang et al., [Better Call Grep: Evaluating and Improving Grep-Like Lexical Retrieval for Repository-Level Code Completion](https://arxiv.org/abs/2601.23254v3) | 首发 2026-01-30；v3 2026-07-29；页面标注 ISSTA 2026 | LLM 生成词法搜索、标识符重排与结构去重；强非图对照 | v1 标题为 GrepRAG；方法并非完全不含结构；结果针对补全而非所有工程任务 |
| S22 | Hu et al., [LARGER: Lexically Anchored Repository Graph Exploration and Retrieval](https://arxiv.org/abs/2605.16352v1)；[全文](https://arxiv.org/html/2605.16352v1) | v1 2026-05-08 | 搜索锚点＋可信局部图扩展；表 3 提供组件消融 | 作者预印本实验；固定参数与按仓库调优的 oracle 设置分开；表 1 中 Claude Code 使用不同模型，不可当完全同模型对比；Acc@k 为全部目标进入前 k |
| S23 | Lin et al., [How Much Static Structure Do Code Agents Need? A Study of Deterministic Anchoring](https://arxiv.org/abs/2606.26979v2)；[全文](https://arxiv.org/html/2606.26979v2) | 首发 2026-06-25；v2 2026-07-02；页面标注 ISSTA 2026 | 轻量结构注释、方向和粒度、导航稳定性的实验思路 | Python、单一 agent；§7 称仅评定位，与其他部分的修复表述有口径张力，本文不采用修复率数字，不把一项研究写成普适准则 |
| S24 | Zhang et al., [SWE-Explore: Benchmarking How Coding Agents Explore Repositories](https://arxiv.org/abs/2606.07297v1)；[全文](https://arxiv.org/html/2606.07297v1) | v1 2026-06-05 | 固定行预算下检索区域的覆盖、排序、效率；多语言评估设计 | 预印本；gold 来自成功轨迹，未穷尽所有有用区域或修复路径；与本项目作者构造、静态标注的口径不同 |
| S25 | Seddik et al., [Context-Augmented Code Generation Using Programming Knowledge Graphs](https://arxiv.org/abs/2601.20810v1) | v1 2026-01-28 | 细粒度代码／文本知识节点、剪枝与重排 | 主要 HumanEval／MBPP；不是复杂私有仓库定位的直接验证 |
| S26 | Li et al., [GraphCodeAgent: Dual Graph-Guided LLM Agent for Retrieval-Augmented Repo-Level Code Generation](https://arxiv.org/abs/2504.10046v2) | 首发 2025-04-14；v2 2025-11-18 | 需求图与结构语义代码图、多跳检索；DevEval／CoderEval | v1 名为 CodeRAG，v2 改名；不同于 CodeRAG-Bench；复合方法不能只归因为结构图 |

数字使用说明：报告对 S22 表 3 的 55.7−48.2 计算为 **7.5 个百分点**，不是 7.5% 相对增幅。论文表中百分比变化列与正文措辞并不完全一致，因此本文只采用明确的原始数值及自己的减法。没有将跨论文百分数合成排名。

## 产品、官方文档与开源实现

| ID | 官方来源与 URL | 首发／版本状态 | 能支持什么 | 证据边界 |
| --- | --- | --- | --- | --- |
| S2 | [Microsoft GraphRAG documentation](https://microsoft.github.io/graphrag/) | 持续更新；首页未给稳定文档版本；采用访问日快照 | 实体图／社区处理及 local、global、DRIFT、basic 查询模式 | 官方功能说明；不是针对代码的独立效果证明 |
| S3 | [microsoft/graphrag](https://github.com/microsoft/graphrag) | 访问时主分支 README；本次未固定 commit | 作者实现、索引成本提醒、版本迁移提示 | 未在本项目安装或跑完整 GraphRAG；仓库存在和 stars 不证明采用率或效果 |
| S10 | [Sourcegraph Cody Context](https://sourcegraph.com/docs/cody/core-concepts/context) | 持续文档，页面标注 Latest，未给可确认首发日期 | 关键词、Sourcegraph Search、Code Graph 等上下文来源 | 产品自述；没有各组件流量占比、内部完整策略、受控消融或市场份额 |
| S11 | [VS Code: How Copilot understands your workspace](https://code.visualstudio.com/docs/agents/reference/workspace-context) | 页面页尾标注 2026-10-07；访问快照 | 语义搜索、文本／grep、文件、usages、读取与迭代；索引可用性 | 不能由当前说明倒推历史所有版本；也不能等同所有 Copilot 客户端行为 |
| S12 | [GitHub: Indexing repositories for GitHub Copilot](https://docs.github.com/en/copilot/concepts/context/repository-indexing) | 持续更新，未标可确认首发／修订日 | Copilot Chat／cloud agent 语义索引、刷新和权限说明 | 服务方文档；刷新时间是产品描述，非本地实测；非 GitHub 索引的策略需读具体条款 |
| S13 | [Continue: @Codebase (Deprecated)](https://docs.continue.dev/reference/deprecated-codebase) | 当前已弃用；页面保留 Legacy Documentation；无确定弃用发布日期 | **历史** embedding＋关键词检索及可选重排；明确弃用状态 | 不可称当前 Continue 全产品实现；原页中的“currently”位于旧文档区 |
| S14 | [Continue: Agent codebase and documentation awareness](https://docs.continue.dev/guides/codebase-documentation-awareness) | 当前迁移推荐指南；无可确认首发／修订日 | agent 文件／搜索工具、rules、MCP、自建 code RAG 选项 | 不是完整内部检索架构或独立性能验证 |
| S15 | [Aider: Repository map](https://aider.chat/docs/repomap.html) | 持续文档；无固定版本号 | 符号／签名地图、文件依赖图排序、上下文预算 | 产品实现说明；不是完整调用图或图相对其他方案的公平评测 |
| S16 | [Aider: Building a better repository map with tree sitter](https://aider.chat/2023/10/22/repomap.html) | 官方文章 2023-10-22 | repomap 的历史设计背景与解析器选择 | 历史材料；不能直接当作所有当前版本的逐行实现说明 |
| S17 | [Tree-sitter introduction](https://tree-sitter.github.io/tree-sitter/) | 持续文档；未标首发／版本 | 增量解析、构造源文件语法树 | 解析能力不等于全程序名称／类型／调用解析 |
| S18 | [SCIP Code Intelligence Protocol](https://github.com/scip-code/scip) | 原 sourcegraph/scip URL 跳转到 scip-code/scip；主分支访问快照，未固定 commit | 代码导航协议与语言索引器入口 | 协议支持某种关系不证明某索引器对所有语言特性都完整 |
| S19 | [Sentence Transformers: Retrieve & Re-Rank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) | 持续文档；页面无可确认版本日期 | 先召回候选，再交叉编码器重排的机制 | 通用 IR 教程；代码领域的收益仍需实测；不是本实验已经跑过 reranker |
| S27 | [ozyyshr/RepoGraph](https://github.com/ozyyshr/RepoGraph) | 作者仓库主分支 README；访问快照，未固定 commit | 图构建、NetworkX 输出及 SWE-agent／Agentless 集成入口 | 有可检查代码不等于可直接投产或已独立复现；README 也提示当前构建较慢 |
| S28 | [gersteinlab/LocAgent](https://github.com/gersteinlab/LocAgent) | 作者仓库主分支 README；访问快照，未固定 commit | LocAgent 的作者实现和复现入口 | 本项目没有运行其训练／完整 agent；不依据 stars 推断“主流” |

## 检索了但没有据此扩大结论的材料

- [SWE Context Bench v3](https://arxiv.org/abs/2602.08316v3)：首发 2026-02-09，v3 2026-05-06。原文当前重点是相关任务间的历史经验复用，不能当成静态代码图优于 hybrid 的证明。检索到的二手描述与 v3 范围有差异，因此报告没有采用二手数量或结论。
- [CodexGraph v3](https://arxiv.org/abs/2408.03910v3)：首发 2024-08-07，v3 2026-07-27。核实其“agent 查询代码图数据库”的设计；报告已有直接图研究覆盖同类取舍，没有堆砌另一个排名。
- [2025 年代码 RAG 综述 v1](https://arxiv.org/html/2510.04905v1)：只用来发现原始论文；方法事实与成绩返回对应原文核验。二手综述、媒体、模型生成的论文摘要均未作为产品内部架构或性能的最终依据。

## 本地实测证据独立于文献

[实验复现说明](reproduce.md)、[机器生成汇总](../results/summary.md) 与其原始数据是本项目本地实验的依据。引用论文不等于复现论文。本地旧版本源码、模型 revision、查询哈希和参数以这些实验文件为准；若文献建议与实际实现不同，报告须分别标为建议与实测，不能相互冒充。

阅读网页和作者仓库不是软件供应链审计；本次也没有替作者验证每个表格、统计假设和生产承诺。证据边界保留在报告中，而非只藏在参考文献末尾。
