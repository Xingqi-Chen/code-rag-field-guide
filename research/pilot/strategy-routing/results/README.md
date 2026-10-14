# 统一GraphRAG路由：完成结果与复算

2026-10-14完成92个单元：23个唯一问题×4方法，86份最终回答、6份失败。图、语料、问题和评分规则保持冻结。GraphRAG在回答前只按问题文字选Local／Global／DRIFT，是一个方法；没有失败后换路线，也没有看分数选策略。[中文解释及完整结果](../../../../docs/report.md)是主报告，本页只说明数据与复算。新增[四个本轮原因案例](../../../../docs/report.md#本轮为什么表现不够好)沿实际调用、材料和回答逐层核查，解释失败和反例，不改评分。

主test16必要要点完成分：GraphRAG 55.4%、BM25 70.4%、Basic 79.1%、hybrid78.1%。dev4、补充6题单列；重叠三题复用同一答案。失败保持0分，满分不代表额外细节全部正确。所有评分为AI审阅，隐藏标签不能保证版式不泄露方法；没有独立人类评分。

## 文件怎样对应

- [execution.json](execution.json)：最终公开账本，含92个单元摘要、193个调用事件、限额和累计计数；私有完整账本仅发布SHA，不发布凭据或私人路径。
- [cells](cells)：每题方法的最终答案、失败原因、各步材料、实际发送证据和去重原文来源。仅组装但未确认发送的材料不计实际覆盖。
- [wire](wire)：逐次请求体与规范化可见回复。原始HTTP／SSE事件流未留存；六个decoder错误不能进一步判定空消息或多消息。embedding保留模型、用量、数量、维度和完整私有响应SHA，不分发向量。
- [scores.json](scores.json)：全部92个要点分、原文覆盖、主／dev／补充分组、逐题配对及固定种子的描述性bootstrap。`ordered_unique_raw_source_mrr`仅为跨子调用首次曝光顺序诊断，不等于旧单次检索MRR。
- [evidence-scores.json](evidence-scores.json)：独立必要要点材料支持、现有引用组的解析／位置／支持情况；不与内容分加权混成总分。
- [grading-packs](grading-packs)、[grading-method-map.json](grading-method-map.json)：实际匿名答案和完成后的方法映射；内容审阅先冻结，随后才给实际材料。
- [evidence-manifests](evidence-manifests)：第二阶段每批及每个实际材料包的SHA。验证脚本可仅用公开的wire、cells和内容审阅重建全部7批材料，与审阅输入逐字一致，无需私有缓存。
- [逐项审阅](../reviews)：7批内容与7批证据审计、独立执行和脚本检查，保留理由、原句和来源；部分内容审阅里的“evidence pending”是其冻结时状态，后续独立文件记录完成。
- [execution-statistics.json](execution-statistics.json)：不重复计重叠题的23题成本，区别预留／派发／成功、common计数／provider usage、已知／未知。没有把23题混成一个效果均分。
- [export-manifest.json](export-manifest.json)：本目录全部JSON哈希；导出不读凭据、不联网。

## 免费离线复算

在仓库根目录运行，Python标准库即可；这些命令不读取私有运行目录、不访问模型、不会产生模型费用：

```sh
python3 research/pilot/strategy-routing/verify.py
python3 research/pilot/strategy-routing/runtime/verify_runtime.py
python3 research/pilot/strategy-routing/aggregate_results.py --check
python3 research/pilot/strategy-routing/aggregate_evidence.py --check
python3 research/pilot/strategy-routing/summarize_execution.py --check
python3 research/pilot/strategy-routing/verify_results.py
```

`verify_results.py`重建7份实际证据审阅包，核验92个单元、请求／回答哈希、限额、全部评分及导出清单。它复算已有判断，不声称程序能取代逐条判断事实。CI运行这些轻量检查，不跑长实验或模型。

## 实际运行与边界

本机环境是Mac mini M4、10核CPU、16 GiB、macOS26.4.1，隔离环境Python3.12.10，Microsoft GraphRAG v3.3.0固定commit `5faaaf4f5685fa2056fa8c3bf9342cb089f2942f`。语料是Requests 2.32.3固定commit `0e322af87745eff34caffe4df68456ebc20d9068`，41个文件／114块，遵循原[下载和建索引方法](../../full-run.md)。种子20261012；生成服务返回标识gpt-5.6-luna，向量为OpenAI text-embedding-3-large／3072维。实际模型后端身份不能独立核实。

实际执行代码来自commit `64f2bfcd5c0d5e6707d53b409b94bd068f5b74d8`（最初未派发故障来自`0ce19ba85b3d46e34c81bf35c2f1b187aabe8301`）。在已授权、已配置依赖和本地缓存的环境运行：

```sh
caffeinate -i env PYTHONHASHSEED=20261012 PYTHONDONTWRITEBYTECODE=1 \
  .cache/graphrag-venv/bin/python research/pilot/strategy-routing/runtime/runner.py execute \
  > .cache/pilot/strategy-routing-run.log 2>&1
```

这条是**已发生的付费执行命令**，不是免费验证命令。运行器有输入／实现哈希门禁和已完成请求缓存；原冻结输入含本机索引文件哈希，重建后的二进制向量库可能不同，跨机器重跑需重新核验并生成新的运行记录，不能冒用本轮哈希或覆盖既有结果。远端模型也不能保证逐字再现；公开结果的离线复算可以精确重现。用户于04:24:49 UTC明确授权付费调用与材料发送，未新增账户或凭据权限。

先前[冻结方案](../README.md)中的“等待上限确认”和[离线验证](../runtime/offline-verification.json)中的“零真实调用”是当时的状态，保留其原哈希。之后用户授权累计上限1883；一次旧调度器冲突在派发前停止，修复后继续，原预留未删除。所有真实步骤／时间见账本和独立[执行审计](../reviews/final-execution-review.json)，不是只有计划或合成mock。

本轮新增149次生成预留、148次实际派发、44次embedding；142次生成有成功HTTP200结果，6次用量未知。最终累计1498次生成预留、3,095,030 common-input token、666,553 embedding token。6份成功回复超请求2048输出上限。生成美元费用、峰值内存未测；共同上限不等于等总上下文，基线旧上下文缓存也使本轮时间不能当生产延迟排名。

未完成／未测试：新补丁和回归执行、等实际源码量或随机邻居消融、独立人类评分、跨仓库泛化、更多语言、通用agent搜索和reranker。本轮只比较固定路由配置，不能把六个服务／适配失败全归因于GraphRAG算法，也不能删除后宣称胜过基线。
