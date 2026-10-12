# 真实项目试点准备：先用 Requests 检查微软代码索引

**准备完成，效果尚未测。** 截至 2026-10-12，在 Mac mini 上固定了代码、输入、20个检索问题和2个小功能任务，跑通了受控本地测试。获准的接口探测已发送1次生成请求，收到HTTP 401后立即停止；embedding调用为0，没有微软索引、召回成绩或补丁成果。见[最新真实记录](probe-result.md)。

可以把这一步理解成先备好同一批书、同一张考卷和评分规则，再让普通搜索与微软图检索参加比较。不能先看哪种方法表现好，再换考卷。

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

## 已准备好的材料

| 项目 | 实际状态 |
| --- | --- |
| 输入 | 41文件，429,368字节、12,705行；18源码、15测试及8文档/配置文件 |
| 统一切块 | 原文98,648个 `o200k_base` token；114块，含整行重叠105,656 token；每块至多1200；1个空测试模块不索引 |
| 检索题 | 20题：定位6、调用6、有限影响6、无实现1、运行时未知1；4 dev / 16 test |
| feature | F01 字典合并运算；F02 Session默认超时；各从相同修改前版本开始 |
| 本地回归 | 59项通过；这是所选离线子集，不是 Requests完整测试套件 |
| 新功能验收前测 | F01：4失败/3通过；F02：10失败/4通过，失败来自功能缺失；没有生成/应用解决补丁 |
| 微软接入 | v3.3.0配置字段/接口已静态核对；已选生成与embedding模型；第三方endpoint及运行适配仍未验证 |

大小来自 [size.json](size.json)，逐文件hash见 [files.json](files.json)。原始本地输出见 [回归日志](regression.log)、[F01前测](feature-F01-before.log)、[F02前测](feature-F02-before.log)。环境为 Apple M4、10 CPU、16 GiB、macOS26.4.1、Python3.12.10；工具实测版本见 [environment.json](environment.json)。只安装了小型测试／token计数依赖，没有下载新权重或安装微软依赖。

题目与来源已独立核证后冻结，见 [协议](protocol.md)、[问题](questions.json)、[必要证据](gold.json)、[feature规范](features.json)、[feature证据](feature-gold.json)、[冻结清单](freeze.json)。开发题只做兼容性检查，不调召回参数；测试题也不代表整个行业。影响分析标注的是“必须检查的有限证据”，不是“所有文件都必须修改”。

## 下一轮究竟比较什么

先对比 **BM25、同模型hybrid、Microsoft Basic、Microsoft Local** 交回的代码证据，另保留便宜的精确文本/符号参考。共享embedding、源码块和4,000/12,000-token最终预算；图关系与社区文字也占预算。只取上下文时必须绕开会继续生成答案的公共search API，使用固定版本内部builder，接入边界见 [接口说明](interfaces.md)。

之后才把各组相同预算的材料交给同一个编辑模型完成两个feature，分别检查新增验收、旧回归和人工需求满足。仅有检索数据时，只能说检索效果，不能推断代码修改成功率。目前只提供 [离线排名函数](baselines.py)；完整微软运行适配器、上下文序列化和评分聚合器仍须接通并机械验收，不能把准备代码称为已跑通实验。

## 已选模型与下一步限额

生成使用 **one.fullstar.tech `gpt-5.6-luna`**；hybrid／Basic／Local统一使用 **OpenAI官方 `text-embedding-3-large`，3072维**。这是用户后续选择，原冻结模板、问题和协议保持原hash；新增[选定配置](ms-settings.selected.yaml)与[选择清单](selection.json)记录变化，不冒称在原冻结时已决定。

**用户已批准并执行一次[8块兼容性探测](probe.md)范围内的尝试**：生成最多17次发送、每次最多请求2048输出token、60秒超时；embedding最多3批、累计20,000个cl100k输入token、30秒超时；不自动重试，并发1，总时长20分钟。按官方普通输入单价，OpenAI embedding输入费上限约 **$0.0026税前**，批准总预算$0.01；用户已明确one.fullstar不必估价。实际首次认证失败即停，已关闭本批，OpenAI实际调用为0。密钥由用户手动放在仓库外，见[凭据说明](credentials.md)。

原[文本token情景测量](token-estimate.json)仍可复算：8块初抽加补抽成功时共16次逻辑请求，输入36,480–52,864个o200k文本token；全部114块为228次、609,410–842,882。这只计算抽取，并以每次2048可见文本token为假设，**不是完整索引预算**；不含角色封装、描述汇总、社区报告、图产物embedding或改码。现在另用embedding实际词表cl100k重算8块加4dev，共4,327 token，见[结果](embedding-estimate.json)。两种计数口径不能混用。

第三方endpoint已由公开API文档核实；模型映射、schema与远端限额语义未通过验证。独立HTTP探测脚本的发送前配额和总超时已接通并离线测试；用户随后取消的RSS监控已移除；选定YAML仍是原准备快照，完整微软运行集成尚未完成。

## 可运行的准备命令

从研究仓库根目录，用Python3.12隔离环境（不安装Requests项目、不运行setup.py）：

```bash
python3.12 -m venv .cache/pilot-venv
.cache/pilot-venv/bin/python -m pip install -r research/pilot/requirements.txt
.cache/pilot-venv/bin/python research/pilot/prepare.py --fetch
python3 research/pilot/verify.py --source
.cache/pilot-venv/bin/python research/pilot/run_tests.py regression
.cache/pilot-venv/bin/python research/pilot/run_tests.py F01
.cache/pilot-venv/bin/python research/pilot/run_tests.py F02
```

后两条在原版预期返回exit1，不能把它们放进要求全绿的CI。脚本只选择经审查的离线测试，阻断TCP/DNS并替换个人netrc/proxy读取；它不是执行任意未知补丁的安全沙箱。若要核算微软提示词，先按[源码核对说明](../process.md)下载固定引用文件，之后运行 `.cache/pilot-venv/bin/python research/pilot/measure.py` 即可；其所需prompt已包含在固定引用文件中，不必另下载完整微软归档。此脚本不会调用模型。

发布CI仅执行冻结／选择清单检查及现有轻量测试，不下载语料、不跑微软或feature前测。冻结复核、许可、隐私检查和未完成项见 [准备复核记录](review.md)。
