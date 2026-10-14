# 研究材料导航

研究对象是微软 v3.3.0 的代码索引／上下文检索能力，按精确定位、调用追踪、修改影响、feature 四项任务组织。主文在[中文分享报告](../docs/report.md)。以下材料用于核对与追溯，不必按顺序读完。

- [研究计划](plan.md)：研究问题、直接证据标准与调用边界。
- [通俗原理说明](../docs/graphrag-explained.md)：用同一个原创小店解释BM25、dense／Basic、RRF hybrid及Microsoft Local／Global，区别通用思路与实测参数。
- [官方原理与固定源码核对](implementation.md)、[版本与文件哈希](microsoft-version.json)。
- [直接代码证据及排除项](direct-evidence.md)、[检索记录](search-log.md)。
- [Requests真实项目准备包](pilot/README.md)：题集与协议、隔离输入、实际离线测试；完整索引、首轮168份及离线补测160份上下文、8次功能尝试均已完成；补丁均无法应用，未进入测试。
- [接口探测历史](pilot/probe-result.md)：四批请求与失败单独记账，不当作检索效果。
- [正式评测方法](pilot/full-run.md)、[执行范围](pilot/full-run-plan.json)、[完整索引账本](pilot/results/execution.json)、[真实中断记录](pilot/results/execution-interrupted.json)：639实体、1069关系、84社区报告；[逐题检索评分](pilot/results/scores.json)、[功能原输出和诊断](pilot/results/features)。
- [8000／16000离线预算补测](pilot/results/budget-supplement)：保留4000／12000，新增模型调用为0；[四档实际长度与重叠](pilot/results/budget-supplement/budget-analysis.json)。
- [Global六题真实回答补充](pilot/results/global)：复用84份社区报告，42次map＋6次reduce，与6次同模型BM25回答对照；[冻结协议](pilot/global-plan.json)、[题目](pilot/global-questions.json)、[评分依据](pilot/global-gold.json)和全部请求／回答公开，独立于原有检索分数。
- [失败链、阶段成本与更新语义](pilot/results/failure-analysis/README.md)：原样抽取见证、错误传播、引用核验及四例无网络更新函数微测；不新增模型调用，不改旧结果。
- [代码提示词＋实体类型完成结果](pilot/results/code-prompt/README.md)：第二次完整索引、80份新Local上下文、400行合并分数及逐题／格式独立复核；未新增Global或功能生成。
- [下一轮统一GraphRAG路由方案](pilot/strategy-routing/README.md)：保留题型／评分冻结；[独立运行器](pilot/strategy-routing/runtime/README.md)已完成离线检查，用户已批准累计生成上限1883。
- [本轮过程与发布检查](process.md)。
- [旧版与正常 Git 历史](legacy.md)：旧自制代码图实验退出新版证据。

文献检索截止及访问日：2026-10-12；执行状态更新至2026-10-14。区分三种表述：**已确认的机制事实**由官方文档／固定源码支持；**效果证据**要求实际评测且身份可核实；**试点建议**是基于已知机制和证据缺口的判断，不能当作实测结果。
