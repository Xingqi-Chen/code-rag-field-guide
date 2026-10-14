# 统一 GraphRAG 题型路由：执行前冻结方案

状态：**离线准备完成，等待生成记录上限确认；真实新模型调用为0。** 这是下一轮方案，不是新实验成绩。先前完成结果固定在commit `452448a31c61d64d5ea80adeeb54e8a851feac3d`，不重建图、不覆盖旧结果。

把同一位图书管理员分成三种工作方式：找具体条目用Local，理解全馆主题用Global，需要追问的任务试DRIFT。**三种方式合起来是一个方法**，与BM25、Basic向量和hybrid比较。不是每题都跑三种方式，不按分数挑最好的一个。

## 问题、路由及分母

原[20题](../questions.json)及split不变；路由程序只读取问题文本，不读取kind、gold或分数。按以下顺序匹配规范化英文文本，完整正则见[routing_rules.py](routing_rules.py)：

| 顺序 | 文本规则 | GraphRAG路线 | 含义与待验证假设 |
| --- | --- | --- | --- |
| 1 | 全局职责／架构表达，如distributed across、module responsibilities | Global | 用粗粒度社区报告回答跨模块概览；不是自动证明所有架构题都适合 |
| 2 | trace、起始follow、fallback | DRIFT | 跨步骤追踪尝试先导读再追问；fallback只是这套固定文本分类规则，可能误分类 |
| 3 | 起始if、when changing、plan the following feature | DRIFT | 尝试寻找改动关联及规划证据，仍可能漏掉影响范围 |
| 4 | 其余（含精确定位、负例、运行时未知） | Local | 固定回退；不因答错或失败改换路线 |

[逐题路由清单](queries.json)已保存。主组20题是8 Local＋12 DRIFT；其中test16（含Q19负例）、dev4。**回答内容评分按test16平均，原文检索覆盖仍按有gold的test15平均**，Q20有选择规则证据，Q19不进入召回分母。

原[Global六题](../global-questions.json)另列补充表，不与20题混成一个统计分母。Q01/Q07/Q13与主组重合，直接复用本轮对应方法的新答案；只额外运行F02-plan、G01、G02。补充表路由为1 Local、3 DRIFT、2 Global。总共23个唯一问题、4个方法、92份预期最终答案；唯一问题的路由分布8 Local、13 DRIFT、2 Global。旧Global答案不能充作本轮同模型对照。feature只评规划，不生成补丁或宣称测试通过。

这是已见题目的探索性比较，不是新盲测。文本路由在看新结果前固定，但研究者已知旧结果；不能据本轮证明路由规则能泛化。

## 官方实现与受控配置

固定Microsoft GraphRAG v3.3.0、commit `5faaaf4f5685fa2056fa8c3bf9342cb089f2942f`，安装模块与固定源码hash已匹配。复用代码配置图：1628实体、2891关系、372份报告；官方level2适配实际选367份报告，全部3072维报告向量已存在。Global的概览路线固定level0，共23份报告，官方12k分批实际得到4批。此层级选择在新结果前固定，不宣称等同默认level2全量Global。

DRIFT实际包含：生成假设回答（HyDE）并做向量查询→用相关报告产生初答与追问→两轮最多四个Local子查询→汇总。它的“图”是实体关联和问题探索结构，**不是静态调用图**；两轮也不保证沿同一条调用链走两跳。

本轮限制`drift_k_followups=2`、`primer_folds=1`、`n_depth=2`；每次Local子查询4000-token上下文，源码／社区份额0.5／0.15，实体及关系候选各10。官方默认分别为k20、folds5、depth3，不能把本轮称为默认DRIFT。Local单路线及三种基线用12000上下文；原20题直接复用已有12000材料。官方Global map上下文12000，reduce按16000单请求限制检查。

并发1、每请求16000输入、每题每方法累计64000输入（含所有子步骤和重试）必须由新运行器强制；官方DRIFT中的`concurrency`等字段本身并不在全部实际路径限流。输入超过限制时保留失败，不偷偷缩短、跳步或改路线。

官方HyDE使用`secrets.choice`选模板，未完成追问在无scorer时随机洗牌。本轮预先把模板选取固定为`sha256(20261012:原问题:report_id)`最小项，保存ID/hash；动作洗牌使用每题独立固定seed的Random，保持官方洗牌行为。每题新建QueryState，固定进程hash seed。这是显式随机性适配，不声称完全未改官方随机选择，也不能消除远端生成的不确定性。

所有方法使用同一已有获授权生成服务和模型。向每个生成子调用统一加入“仅以给定快照证据作事实陈述、保持引用、承认未知”的约束；HyDE和追问只是搜索计划，不能当源码事实。官方DRIFT提示本来允许一般知识，统一限制必须公开为提示适配。旧adapter不支持DRIFT全部schema／stream参数，须在新独立运行器中适配及离线mock验证，不能直接启动旧索引运行器。

## 评分与公平性

主表一行是统一GraphRAG，其他行为BM25、Basic、hybrid。最终回答按执行前[必要要点评分](answer-gold.json)计0／0.5／1，按题平均；事实错误、无依据断言及引用支持另外记录，不用回答长度或自评score当质量。独立AI审阅隐藏方法标签、按固定seed排列；版式可能泄露方法，明确不是人类盲评。

检索另表记录每条路线**所有实际读源码的步骤中，原文证据的去重并集覆盖**。DRIFT中间答案、报告描述和HyDE都不算源码。再单列最终生成调用看到的原文量：DRIFT／Global reduce通常只读中间材料，不能把之前读过的源码说成直接交到最终提示中。最终答案的事实正确与其引用是否受实际材料支持分别检查。

每题记录所有物理调用、重试、输入／输出usage、可复算common-token、各步材料总量、源码量／去重量、实际端到端延迟、失败及停止原因。官方DRIFT的`completion_time`在reduce前计算，因此总延迟用外围计时；返回的`context_data`也不含全部HyDE／primer输入，须由逐调用账本补全。所有路线受每题每方法累计64k common-input上限约束；**共享上限不等于相同实际成本**。单轮基线通常只用一部分，DRIFT花在HyDE、追问和多次阅读上的量都要计入。请求输出2048，但现有代理曾忽略该上限，真实用量照录，不能据请求参数保证实际输出或美元费用。

新失败保持在预定分母：没有最终答案的内容覆盖记0并单列失败率；已完成的检索步骤可报告部分原文覆盖，但不能假装成功回答。相同完整响应只用缓存，不重发。一般瞬态错误按原有每请求最多两次额外尝试处理；已授权的确定最小纯JSON修复需留原文和精确diff，不补语义、字段或答案。新风险不自动扩权。

## 预算盘点与唯一待确认项

[离线预检](preflight.json)读取已完成账本，未重置计数。

| 项目 | 已累计 | 本轮最坏上界 | 合计／现有上限 |
| --- | ---: | ---: | ---: |
| 生成记录预留 | 1349（实际派发1347） | 534 | **1883／1600：需增加283** |
| common-input token | 1977136 | 5888000 | 7865136／8000000 |
| embedding token | 658211 | 1632000 | 2290211，累计估价$0.29772743／$1 |
| 当前续接账本embedding尝试 | 103 | 204 | 307／1000 |

正常生成上界：8次Local＋13×7次DRIFT＋2×5次Global＋23×3次基线＝178。DRIFT每题最多1 HyDE＋1 primer＋4 Local＋1 reduce＝7；Global每题4 map＋1 reduce＝5。每个请求最多两次额外瞬态尝试，178×3＝534；不另留隐藏探针、行政预留或额外判分API调用。

embedding保守按13×5个动态查询＋3个新增原问题＝68条／批；每条最多8000 token、每批最多两次额外尝试，故68×8000×3＝1632000。已有源码、报告、实体及原20查询向量复用。最终判分使用独立研究审阅，不额外调用付费judge接口。

64k上限含失败重试，所以极端错误组合可能先耗尽单题额度而未完成；保证的是不超限，不保证任意错误后仍成功。既有生成120秒／embedding30秒、无总截止、并发1、响应字节上限及未知usage保留规则不变。8百万指原账本的common-input计数，不是供应商报告的prompt tokens；后者单独计量。模型生成费用未知，不把embedding估价当总费用。

**需要确认：仅把续接累计生成记录上限1600提升到1883。** 当前余251足够无故障178次，但不足覆盖承诺的完整重试上界，因此本预检不启动付费测试。其余限额不提高。

当前common-input剩余6022864 token，本轮最坏使用5888000，余量134864。没有已授权的累计输出token额度，也无法从每请求2048推导真实输出余量；所有实际输出与未知usage将继续单列。DRIFT参数是在新结果前明确限定的研究配置，不是为了塞入剩余251次而临时改成单次Local。

## 离线复核与来源

[独立预算审查](budget-review.json)确认上述上界；[官方流程合成mock](mock-result.json)实际走通7次假生成、5次假embedding的接口路径，调用数可由[mock_drift.py](mock_drift.py)复跑。**它不访问模型，不是检索或回答效果测试，也不证明尚未实现的新付费adapter已通过。** [回答标准复核](answer-gold-review.json)记录87个必要点与94个源码锚点；它是独立于执行/路由的AI制定者做第二遍一致性检查，不冒称双人盲评。

离线准备：`.cache/graphrag-venv/bin/python research/pilot/strategy-routing/prepare.py`。它拒绝覆盖已有preflight，并用审计钩子禁止网络；不读取凭据。准备失败和修复只影响新脚本，不改旧图或账本。完整执行器须在额度确认后、真实运行前单独通过冻结输入和预算边界检查。

[冻结清单](freeze.json)记录方案、路由、评分标准和审查文件的SHA-256；`python3 research/pilot/strategy-routing/verify.py`可离线核验。[准备验证记录](preparation-verification.json)保留本机实际检查输出。这些记录确认准备状态，不代表已完成本轮回答实验。

- [官方DRIFT文档](https://microsoft.github.io/graphrag/query/drift_search/)：未标发布日期；2026-10-14访问，机制以固定v3.3.0源码为准。
- [微软介绍文章](https://www.microsoft.com/en-us/research/blog/introducing-drift-search-combining-global-and-local-search-methods-to-improve-quality-and-efficiency/)：2024-10-31发布，2026-10-14访问；其新闻数据实验不作为代码效果证据。
- [固定DRIFT检索源码](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/drift_search/search.py)、[HyDE与primer](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/drift_search/primer.py)、[动作选择](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/drift_search/state.py)。

新预检日期不改写旧报告的2026-10-12文献截止；这是后来追加核对。官方代码／提示仍按仓库已有Microsoft MIT归因，原文按Requests Apache-2.0及NOTICE归因。
