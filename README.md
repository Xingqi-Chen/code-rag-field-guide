# Microsoft GraphRAG 适合做开发助手的代码索引吗？

把代码仓库想成图书馆：关键词搜索查原文，向量检索按意思找段落，Microsoft GraphRAG 则先制作“事物卡片”和关系导读。导读可能带来线索；真正改代码，还要找到**具体哪一页、哪个版本、哪些调用者和测试**。

**[阅读中文主报告](docs/report.md)** · [从BM25到GraphRAG：通俗原理](docs/graphrag-explained.md) · [实验方法与复算](research/pilot/full-run.md) · [官方源码与证据](research/README.md)

研究固定 **Microsoft GraphRAG v3.3.0**，文献检索截止 **2026-10-12**，执行状态更新至 **2026-10-13**，聚焦四项开发任务。默认文档实体图与程序的符号／调用图是两种东西，不能因为都有“图”，就认定能解决相同问题。

**本次结果不支持把默认 Microsoft Local 当成代码检索的升级替代。** 在固定 Requests 快照、相同4000-token上限下，hybrid找到的必要源码证据最多，Local明显落后。补测到16000 token后，hybrid仍最高、Local仍最低；这不只是4000小窗口下的观察。这是一个小样本的**检索证据覆盖**结果，不是回答正确率，也不是“所有图检索无效”。

| 方法 | 4000 | 8000（补测） | 12000 | 16000（补测） |
| --- | ---: | ---: | ---: | ---: |
| BM25关键词 | 35.3% | 43.7% | 64.3% | 69.3% |
| 关键词＋真实向量hybrid | **42.9%** | **56.3%** | **71.0%** | **77.9%** |
| Microsoft Basic向量 | 35.8% | 55.8% | 57.4% | 57.4% |
| Microsoft Local实体图 | 5.6% | 21.0% | 21.0% | 23.2% |

主分母是预先保留的15道可评分测试题；另1道无实现负例不计召回，4道开发题单列。证据命中要求实际取回的原文覆盖一段预标证据的至少80%行，再按题平均；严格100%行口径在本批得到相同结果。[首轮原始材料](research/pilot/results/contexts)、[首轮分数](research/pilot/results/scores.json)与[补测结果](research/pilot/results/budget-supplement)可离线复算。相同上限不等于相同实际材料量：16000档Local平均实际11647 token，hybrid15242；Basic受固定10块候选限制。

**代码提示词＋实体类型追加验证：**已冻结配置并真实运行。75→76、96→97经授权重发均成功；107及其获准的两次重试108／109都被本机60秒计时器截断，现因该请求重试额度用尽而停止。累计104份成功结果完整保留，5次未知结果的远端用量仍未知。目前没有完整新图或Local分数，尚不能判断新配置是否改善效果。[中断、恢复关联与超时诊断](research/pilot/results/code-prompt)均保留，旧版结果不外推到该变体。

**新增Global真实回答实验：**复用84份社区报告，对4道精确／规划题和2道全局认证题运行官方map→reduce，再与同模型BM25回答比较。54次调用全部完成，耗时约9分45秒，无新embedding或索引重建。Global能整理较广的职责和测试主题，但精确位置仍有缺口，并出现不存在的报告引用；BM25也有行号及逻辑解释错误。独立AI审阅的必要要点覆盖，精确／规划题为52.5%对81.25%，全局题为45%对65%（Global对BM25）；不是整篇答案准确率。Global总输入是BM25的7.86倍，不能把两组说成等总预算。[逐题回答、审阅与总用量](research/pilot/results/global)与[完整方法](research/pilot/full-run.md)单独记录，不与上表检索覆盖率混算。

**什么时候值得试：**自然语言线索分散，希望它补到基线漏掉的材料，并愿意为抽取、报告、来源核验和更新付出成本。**什么时候不能依赖：**要求唯一符号位置、完整调用者、确定的运行时目标或修改／删除同步。默认文档实体图没有这些保证。实际Q01中，Local取回的实体描述包含正确的字典名称，却没交回实现源码；“听起来知道答案”与“给开发者足够依据”是两回事。

**为什么会这样：**离线追踪发现，字典实现块没有关联到具体字典实体；header类型误述和错误方法名从补抽一路进入报告、Global答案；另一个无效引用是在最终汇总时才出现。Local的来源候选和预算分配、Basic的固定10块上限也影响表现。默认update按新标题追加，对改函数体、删文件和重命名不提供完整同步；四个无网络小表测试核验了相关处理语义。原因按“直接证据／支持但未隔离／待验证”区分，不能把全部差距归给图算法。[原因、阶段成本与代码变更](docs/report.md#效果不好的原因沿着材料流转找断点) · [原样见证与复算](research/pilot/results/failure-analysis/README.md)

实验由Mac mini编排远端模型；不是本地权重推理。完整索引有639实体、1069关系、84报告，518次生成尝试，实际workflow约71.28分钟；保留了失败、唯一获准重发和真实用量。20个检索问题×4组×4档预算，加2个功能任务×4组，共328份上下文已核验；其中新增160份只复用本机索引和向量，外部模型调用为0。两个功能任务的8份单轮补丁全部因diff损坏无法应用，未进入测试，无法据此比较功能正确性。[完整方法与边界](research/pilot/full-run.md)

[四张图](docs/figures/README.md)及[小店代码](docs/examples/shop/README.md)是原创教学示例，**不是微软实验输出**。旧自制代码图实验保留在[正常Git历史](research/legacy.md)，不算新版微软效果证据。[接口探测历史](research/pilot/probe-result.md)与正式评测分开记账。

发布快检不需要网络、凭据或模型：

```bash
python3 -m unittest discover -s tests
python3 -m unittest discover -s research/pilot/tests
python3 research/pilot/verify.py
python3 research/pilot/verify_results.py
python3 research/pilot/score_results.py --check
python3 research/pilot/score_budget_supplement.py --check
python3 research/pilot/verify_global.py --check
python3 research/pilot/analyze_failure_chains.py --check
python3 research/pilot/verify_code_prompt.py
python3 scripts/validate.py
```

评分复算不需要再次调用模型。原创内容适用[MIT](LICENSE)，第三方片段及来源见[许可与归因](NOTICE.md)。[研究过程](research/process.md)保留真实提交、失败与独立复核记录。
