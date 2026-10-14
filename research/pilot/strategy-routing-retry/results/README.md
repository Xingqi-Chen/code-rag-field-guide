# 六个原失败 DRIFT 项：调查、重试与复算

2026-10-14在同一台Mac mini完成。初轮13个DRIFT项是7成功、6失败；只重试Q08、Q10、Q11、Q14、Q16、Q18，六项均完成。原七个成功DRIFT项和全部基线未重跑，原92行结果与失败费用均保留。主报告的[条件重试章节](../../../../docs/report.md#故障修复后的条件重试六项完成效果仍有限)解释结果；本页是文件和命令导航。

## 能确认的结论

- 六项生成成功后，GraphRAG主测试16题必要要点完成分从初轮55.4%变为72.8%；不是全文正确率。原样复用的BM25为70.4%、Basic79.1%、hybrid78.1%。三组题级配对描述区间均跨0，不能宣称稳定胜出。
- 新Q11、Q16 primer分别有两条、一条额外空assistant消息；旧解码器拒绝，新解码器顺序拼接后得到唯一非空JSON，并通过原schema。36份完整新生成回复中其余34份新旧解析相同。旧六次失败原文未保存，不能确证它们也属于这一分支。
- 新记录还确认TLS提前断连被误分为安全故障。按真实EOF异常分类后，在原预算与最多三次累计尝试内恢复；证书验证保持开启。较早一次没有明确SSL子类的失败仍记未知。
- 六个新内容分：Q08 12.5%、Q10 87.5%、Q11 50%、Q14 66.7%、Q16 62.5%、Q18 50%。Q11是dev，不能混进test。Q08恢复调用后仍缺header验证链，说明“有答案”不等于“完成任务”。

这是已知失败后的条件重试；问题、gold、路由、图、参数、提示词、模型和种子不变。不是新的独立样本，也不是只改一个变量的因果实验。原成功题／基线的86行内容分和证据分逐字保留；新内容评分先冻结，再提供检索材料审查证据与引用。全部审阅由独立AI代理完成，没有独立人类评分，匿名标签也不保证完全盲审。

主测试16题材料支持分另算：GraphRAG79.9%、BM25 74.9%、Basic82.0%、hybrid83.0%。GraphRAG原文覆盖43.6%只针对15道可评分检索题；能溯源的图描述可支持事实，却不冒充源码。六份新答案的26组引用均已审阅。

## 文件导航

- [execution.json](execution.json)：六格状态、73次新尝试、预算和原始私有账本SHA。
- [cells](cells)：六份最终答案、追问、上下文、缓存使用和确实送入成功HTTP200请求的源码。
- [wire](wire)：每次请求体、规范化可见回复及不含文本的传输诊断；向量仅保留维度／哈希，不分发原始SSE、隐藏推理、凭据或模型权重。
- [retry-diagnosis.json](retry-diagnosis.json)：独立复核新旧解析、原六失败及新传输问题；[首次停止时的诊断](retry-diagnosis-first-stop.json)保留当时状态。
- [scores.json](scores.json)、[内容逐点审阅](../content-review.json)：以六份新判断覆盖合并表中的六格，原始表不改；dev4、test16和补充6题分开。
- [evidence-scores.json](evidence-scores.json)、[证据逐点审阅](../evidence-review.json)、[实际材料包](evidence-packs)：材料支持与引用核验单列，不与内容混成总分。
- [execution-statistics.json](execution-statistics.json)：新41次生成、32次向量尝试；含失败尝试，费用未知不作0。
- [export-manifest.json](export-manifest.json)：导出文件哈希。运行前的[协议](../README.md)、[解析器修复](../DECODER.md)、[首次TLS停止](../TLS-RECOVERY.md)、[确证EOF修复](../EOF-FIX.md)保留各阶段依据。

## 免费离线复算

从仓库根目录执行，Python标准库即可。不读取本机模型／索引缓存、不联网、不产生API费用：

```sh
python3 research/pilot/strategy-routing-retry/aggregate_results.py --check
python3 research/pilot/strategy-routing-retry/aggregate_evidence.py --check
python3 research/pilot/strategy-routing-retry/summarize_execution.py --check
python3 research/pilot/strategy-routing-retry/verify_results.py
python3 research/pilot/strategy-routing-retry/test_responses_decoder.py
python3 scripts/validate.py
```

复算验证的是已公开判断的计算、文件对应和未重跑86行的一致性，不声称程序能自动判断答案事实。CI仅运行轻量离线检查。

## 实际执行与预算

Mac mini M4、10核CPU、16 GiB、macOS26.4.1；Python3.12.10、固定GraphRAG v3.3.0与Requests2.32.3，完整commit与建图方法沿用[初轮记录](../../strategy-routing/results/README.md)。本机编排与查询既有图，生成和embedding使用用户明确授权的远端服务，非本地权重推理；实际后端模型身份不能独立核实。没有使用浏览器。

首次执行来自commit `2a49f33`；首次精确TLS续接来自`0f481b3`；确证EOF修复及最终续跑来自`9ec7d99`。实际命令：

```sh
caffeinate -i env PYTHONHASHSEED=20261012 PYTHONDONTWRITEBYTECODE=1 \
  .cache/graphrag-venv/bin/python research/pilot/strategy-routing-retry/runner.py execute \
  >> .cache/pilot/strategy-routing-retry-run.log 2>&1
```

这是已发生的付费执行记录，**不是免费复算命令**。运行器绑定本机既有索引与停止快照；新的机器／新重跑必须另建核验记录，不能冒用这些哈希或覆盖历史输出。远端模型不能保证逐字再现。授权、精确恢复门禁、次数和未知用量都在账本与审查文件中保留，未新增凭据或账户权限。

新增公共输入预留124,871 token；已知生成provider输入167,800、输出22,771 token；5次新生成、8次新向量尝试的用量未知。累计1539／1883次生成预留、3,219,901／8,000,000公共输入token、667,077向量token。按冻结$0.13／百万token估算，新增向量预留$0.00006812、累计$0.08672001；非账单，生成美元费用未知。

新增查询执行段426.0秒，另有两段恢复预取的UTC重建时间16.9秒，活跃时间合计约443.0秒；包括失败段及退避，排除等待审查、初始加载。旧费用／耗时另外累计，缓存重复读取不新增物理调用。这不是等缓存生产延迟比较。

五个测试文件按各自说明在独立进程运行，共106项通过。不能把它们放进同一个`unittest discover`进程：边界测试安装的进程级安全审计钩子会阻止其他测试导入名称包含credentials的SDK源码；最初组合执行有2项因此失败，逐文件复核已通过。没有关闭测试的网络／凭据保护。

仍未完成：等实际源码量或随机邻居消融、独立人类评分、跨仓库新题验证、新功能补丁及回归执行、生成费用和峰值内存测量。不据此推导整个行业的GraphRAG优劣或端到端开发成功率。
