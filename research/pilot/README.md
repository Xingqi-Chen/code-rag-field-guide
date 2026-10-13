# Requests：冻结语料、题目和评估入口

**完整索引已完成，正式检索与功能评测尚未完成。** 114块官方索引于2026-10-13结束，得到639实体、1069关系、84社区报告；后续查询受执行许可检查阻拦，未发新请求。[完整执行记录](results/execution.json)、[中断历史](results/execution-interrupted.json)和[接口探测](probe-result.md)分别保存，不能用索引规模推断检索效果。

可以把准备过程理解成先备好同一批书、同一张考卷和评分规则，再让关键词、普通向量和微软图检索参加比较。没有按方法表现换题或改分。

## 为什么选这个项目

主项目是 **Requests**，备用扩展仅列 **Flask**；暂不下载扩展库。选择依据是正式基准记录和首轮工作量，而不是 GitHub stars。

| 官方纳入仓库 | 原 SWE-bench 测试任务数 | Verified 任务数 | 本次判断 |
| --- | ---: | ---: | --- |
| psf/requests | 44 | 8 | HTTP请求准备、认证、重定向、cookie、适配器都有可追踪代码，适合先控制规模 |
| pallets/flask | 11 | 1 | 可作后续不同框架机制的扩展，Verified题数少 |
| pytest-dev/pytest | 119 | 19 | 历史任务快照更大、插件机制更多，暂不做首轮 |

原集计数来自[官方论文 arXiv:2310.06770v3，2024-11-11，表10/12](https://arxiv.org/html/2310.06770v3)。论文表11的历史任务平均规模分别约119/225/497文件、30k/35k/111k行，**不是本次快照的大小**。Verified计数来自[官方统计接口](https://datasets-server.huggingface.co/statistics?dataset=princeton-nlp%2FSWE-bench_Verified&config=default&split=test)，本次返回500条且 `partial=false`；[官方数据集元数据](https://huggingface.co/api/datasets/princeton-nlp/SWE-bench_Verified) SHA为 `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`，更新日2025-02-18，访问日2026-10-12。统计接口是访问时的快照，不假称不可变接口。

使用 **Requests v2.32.3**，commit [`0e322af87745eff34caffe4df68456ebc20d9068`](https://github.com/psf/requests/commit/0e322af87745eff34caffe4df68456ebc20d9068)，提交日2024-05-29。这个已发布旧版本便于隔离复现，**不是最新版本，也不是官方 SWE-bench 的某个 base_commit**。这只是“在正式基准曾采用的真实项目上做原创试点”，不能与榜单直接比较。未采用官方问题／答案patch；模型仍可能见过公开源码，无法保证训练污染为零。

源码为 [Apache-2.0](https://github.com/psf/requests/blob/0e322af87745eff34caffe4df68456ebc20d9068/LICENSE)，保留[官方 NOTICE](https://github.com/psf/requests/blob/0e322af87745eff34caffe4df68456ebc20d9068/NOTICE)归因。完整第三方仓库不发布到本研究仓库；脚本按固定归档hash下载到忽略目录。缓存是独立副本，不修改上游或其他项目。

## 已冻结的材料

| 项目 | 实际状态 |
| --- | --- |
| 输入 | 41文件，429,368字节、12,705行；18源码、15测试及8文档／配置文件 |
| 统一切块 | 原文98,648个o200k token；114块，含整行重叠105,656 token；每块至多1200；1个空测试模块不索引 |
| 检索题 | 定位6、调用6、有限影响6、无实现1、运行时未知1；4 dev／16 test；Q19无gold不计召回分母 |
| 新功能题 | F01字典合并运算；F02 Session默认超时；从同一修改前快照分别开始 |
| 原版离线回归 | 59项通过；是经审查的离线子集，不是Requests完整套件 |
| 新功能前测 | F01为4失败／3通过；F02为10失败／4通过；功能缺失导致预期失败 |
| 微软输入映射 | 固定v3.3.0官方运行时已安装；实际114块逐字一对一分块检查通过 |
| 正式索引 | 已完成；518次生成尝试、46批embedding；唯一不明请求159经授权重发160成功 |

大小见[size.json](size.json)，逐文件hash见[files.json](files.json)。前测实际输出见[回归日志](regression.log)、[F01](feature-F01-before.log)、[F02](feature-F02-before.log)。在用户指定的Mac mini上运行：Apple M4、10 CPU、16 GiB、macOS26.4.1、Python3.12.10。[准备环境](environment.json)与正式运行依赖的[固定版本列表](runtime-requirements.txt)分开保留；后者已经安装，没有下载模型权重。

题目和必要证据由AI研究助手依据源码拟定、独立审阅代理核证后冻结；没有独立人类标注或评分，但均可按源码复查：[协议](protocol.md)、[问题](questions.json)、[证据](gold.json)、[功能规范](features.json)、[功能证据](feature-gold.json)、[哈希清单](freeze.json)。冻结日期为2026-10-12 14:16:24 UTC，早于模型执行。协议中“尚未安装／尚未选模型”等句子是当时状态，不回写历史；后续选择与授权分别由[selection.json](selection.json)和[full-run-plan.json](full-run-plan.json)记录。资源监控后来按用户要求关闭，峰值内存未测。

## 已固定的比较

四组为BM25、同embedding的hybrid、Microsoft Basic与Local。最终上下文共享4000-token主预算和12000-token次预算，图关系、社区报告和来源位置同样计数。另有[精确文本／定义参考](reference-lookup.json)，只是便宜诊断，不冒充完整的引用或调用分析。

生成模型为用户选定的one.fullstar.tech `gpt-5.6-luna`；三组向量部分使用官方OpenAI `text-embedding-3-large`，3072维。模型在远端运行，由Mac mini发起受控请求；代理实际后端映射不能独立核实。成功响应以精确参数缓存，失败不自动重放。正式阶段累计embedding预算$1，旧探针消耗计入；生成价格未知，次数、时间和输入量仍有明确上限。仓库外凭据不入库，见[说明](credentials.md)。

每组对两个功能各生成一次补丁，只使用相同4000-token初始证据，不追加搜索或改错。先核对原始响应／补丁hash与修改范围，再对干净副本跑冻结验收、旧回归和逐项需求检查。当前还没有生成这些补丁。检索覆盖和功能正确性分开报告；两个功能不能组成可靠的行业成功率。

完整原理、预算、实现差异、安装、执行及复算命令统一见[技术附录](full-run.md)，避免维护两套命令。正在使用的检索、打分和补丁检查器已实现并做了合成边界测试；实际168份上下文尚未生成，不能说真实结果验收已通过。

## 现阶段能够离线核验什么

在仓库根目录运行，不读取密钥、不调用模型：

```bash
python3 research/pilot/verify.py
python3 research/pilot/verify_selection.py
python3 research/pilot/verify_probe_result.py
python3 -m unittest discover -s tests
python3 -m unittest discover -s research/pilot/tests
python3 scripts/validate.py
```

已有Requests缓存时，可加 `verify.py --source` 重验71段标注源码。重新获取源码、运行59项原版回归和新功能前测的命令见[技术附录](full-run.md)及[受控测试入口](run_tests.py)；F01/F02在原版预期失败。测试入口的TCP／DNS阻断与个人netrc／proxy隔离是对已审代码的保护，不是任意未知补丁的安全沙箱。

完整结果生成后才运行 `verify_results.py --tokens` 与 `score_results.py --check --tokens`。二者会从实际上下文校验唯一完整网格、原文hash、来源行号、总token和分数；现在缺少结果，不能伪造验收通过。CI只做离线轻量检查。
