# Global 六题真实回答实验

同一 Requests 快照、原有84份社区报告、官方 Microsoft GraphRAG v3.3.0 的真实 map/reduce；对照为同模型一次BM25源码回答。执行于Mac mini，模型在用户选定的远端服务。没有重建索引或新增embedding。

- [运行前冻结协议](../../global-plan.json)、[六题](../../global-questions.json)、[逐项评分与源码证据](../../global-gold.json)。
- [离线调用预算与输入哈希](preflight.json)、[执行前独立复核](preflight-review.json)、[无网络接口检查](offline-interface-check.json)。
- [七批实际map材料](map-contexts.json)、[六份BM25源码上下文](contexts)。
- [54次原始请求／可见响应](calls)、[12份最终回答及map解析结果](answers)、[逐次执行账本](execution.json)、[实际运行日志](run.log)。
- [精确／规划题独立AI评分](review-precise.json)、[全局题独立AI评分](review-global.json)、[可复算分数及完整用量](scores.json)。

运行共584.54秒：42 map＋6 reduce＋6 BM25，全部完成，零重试；provider输入694,712、输出49,786 token。Global总输入为BM25的7.86倍，两组不是等总计算预算。三次BM25的provider输出超过请求上限，原样记录；原图抽取异常也没有修复。所有源码／报告和模型输出都是待核查证据，不因生成成功就成为事实。

评分是冻结必要要点的0／0.5／1人工可检查AI判断，另列错误、遗漏和出处；不是人类盲评准确率。四道精确／规划题与两道认证全局题分开，均不混入原来20题的检索Recall。F02-plan只评价规划，没有新增补丁或功能测试。

在仓库根目录离线复算，无网络、密钥、模型或私有索引要求：

```bash
python3 research/pilot/verify_global.py --check
```

本机另用已有隔离环境和tokenizer重数输入／可见输出：

```bash
.cache/graphrag-venv/bin/python research/pilot/verify_global.py --check --tokens
```

公开调用材料含原始官方提示词和Requests原文／衍生报告，相应归因与许可见[NOTICE](../../../../NOTICE.md)。完整解释放在[中文报告](../../../../docs/report.md)与[方法附录](../../full-run.md)，避免再维护一份重复报告。
