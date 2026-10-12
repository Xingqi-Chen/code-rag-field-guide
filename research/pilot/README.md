# 真实项目试点准备：先用 Requests 检查微软代码索引

**准备完成，效果尚未测。** 截至 2026-10-12，在 Mac mini 上固定了代码、输入、20个检索问题和2个小功能任务，跑通了受控本地测试。没有调用生成或 embedding 服务，没有微软索引、召回成绩或补丁成果。

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
| 微软接入 | v3.3.0配置字段/接口已静态核对；模板非可直接运行配置，模型/provider/维度仍是占位符 |

大小来自 [size.json](size.json)，逐文件hash见 [files.json](files.json)。原始本地输出见 [回归日志](regression.log)、[F01前测](feature-F01-before.log)、[F02前测](feature-F02-before.log)。环境为 Apple M4、10 CPU、16 GiB、macOS26.4.1、Python3.12.10；工具实测版本见 [environment.json](environment.json)。只安装了小型测试／token计数依赖，没有下载新权重或安装微软依赖。

题目与来源已独立核证后冻结，见 [协议](protocol.md)、[问题](questions.json)、[必要证据](gold.json)、[feature规范](features.json)、[feature证据](feature-gold.json)、[冻结清单](freeze.json)。开发题只做兼容性检查，不调召回参数；测试题也不代表整个行业。影响分析标注的是“必须检查的有限证据”，不是“所有文件都必须修改”。

## 下一轮究竟比较什么

先对比 **BM25、同模型hybrid、Microsoft Basic、Microsoft Local** 交回的代码证据，另保留便宜的精确文本/符号参考。共享embedding、源码块和4,000/12,000-token最终预算；图关系与社区文字也占预算。只取上下文时必须绕开会继续生成答案的公共search API，使用固定版本内部builder，接入边界见 [接口说明](interfaces.md)。

之后才把各组相同预算的材料交给同一个编辑模型完成两个feature，分别检查新增验收、旧回归和人工需求满足。仅有检索数据时，只能说检索效果，不能推断代码修改成功率。目前只提供 [离线排名函数](baselines.py)；完整微软运行适配器、上下文序列化和评分聚合器仍须在模型确定后接通并机械验收，不能把准备代码称为已跑通实验。

## 费用：已有规模，尚无服务报价

当前未选服务／模型，**不填写美元预算**。下面是可复算的请求与文本token测量，不是账单或费用上限。

默认抽取每块一次初抽、一次补抽；第二次会重新发送原提示及第一次结果。按“每次结果最多2048个共同计数token”的**估算情景**：

| 抽取范围 | 成功时逻辑completion请求 | 输入文本token情景范围 | 输出文本token情景范围 |
| --- | ---: | ---: | ---: |
| 固定种子选8块兼容样本 | 16 | 36,480–52,864 | 0–32,768 |
| 全部114块 | 228 | 609,410–842,882 | 0–466,944 |

这不含角色封装、重试、实体/关系描述汇总、社区报告或改码。2048只是估算条件，尚未落实为服务端限额；不同模型的实际tokenizer和计费不同，不能把表中上界当总预算。原始数值与8块ID见 [token-estimate.json](token-estimate.json)，由 [measure.py](measure.py)对固定微软prompt和真实输入计数。

源码embedding的已知量是114段、105,656个共同计数token；22个查询正文共682 token。按每批1–16段，源码阶段是8–114个逻辑请求；共享查询缓存可避免方法间重复，但批量限制须以服务支持为准。Local需要实体描述embedding；本模板还配置了社区报告embedding，但Local上下文构建本身不依赖后者。两者数量和长度依赖实际索引产物，当前未知。描述汇总、报告拆分与重试同样不能仅凭源码行数准确估计。

可行候选：

- **托管官方接口：**例如 OpenAI `gpt-4.1-2025-04-14` completion + `text-embedding-3-small`统一embedding。官方列出前者的结构化输出和固定snapshot，后者提供embedding；只是兼容候选，不是已选或已测配置。[completion文档](https://developers.openai.com/api/docs/models/gpt-4.1)、[embedding文档](https://developers.openai.com/api/docs/models/text-embedding-3-small)，访问2026-10-12。实际可用性、维度、token限制和计价须确认；不读取其他项目key。
- **本地兼容服务：**llama.cpp官方server文档列出chat、JSON schema和`/v1/embeddings`端点，但模型、pooling、输入容量和微软适配仍要实测。本轮没有下载或选定本地权重；16GiB硬件不能直接保证某组合稳定。尤其不能把现有MiniLM的256-wordpiece输入上限当成1200-token代码块可用。[官方server说明](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)，访问2026-10-12（动态文档，执行时另固定commit）。

**最小下一步批准项：**选择completion和统一embedding的服务/模型，以及仅8块兼容探测的请求、token、时间/内存上限；若用收费服务，再依据该服务当日官方单价确认金额上限。还须明确使用本项目获授权的凭据方式，不能复用其他项目秘密。先落实计数/停机机制、验证格式和来源，再决定114块完整索引预算。此处没有把任何模型调用视为已获批准。

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

发布CI仅执行 `python3 research/pilot/verify.py` 及现有轻量测试，不下载语料、不跑微软或feature前测。冻结复核、许可、隐私检查和未完成项见 [准备复核记录](review.md)。
