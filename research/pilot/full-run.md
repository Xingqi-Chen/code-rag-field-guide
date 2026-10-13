# 完整评测的执行与复算说明

这是主报告的技术附录；结论与汇总只在[主报告](../../docs/report.md)维护。题集、证据和评分协议见[冻结协议](protocol.md)，本轮授权与运行界限见[运行计划](full-run-plan.json)。

**完整索引、168份检索上下文和8次单轮功能生成已完成。** 结果与来源通过离线验证；8份补丁均在原样应用检查中损坏，功能验收和回归未执行，不把未测当测试0分。效果解释统一见[主报告](../../docs/report.md)，逐题见[分数](results/scores.json)、[检索材料](results/contexts)、[功能记录](results/features)；实际索引见[执行账本](results/execution.json)与[规模记录](results/index-summary.json)，发布前[独立数值与公平性复核](results/evaluation-review.json)未发现阻断问题。

## 比较的究竟是什么

固定 Requests 2.32.3 的 41 个源码、测试、文档和配置文件，共114个完整行文本块。四组是 BM25、BM25＋真实 embedding 的 hybrid、Microsoft Basic、Microsoft Local。后两组使用固定 v3.3.0 官方内部上下文 builder；没有调用其回答生成 API。Local 的图由官方 Standard 流程生成，默认实体类型与抽取／摘要／社区提示词不改。

共享输入按完整行预切块，微软第二次切块设置1200/0，并实测逐字一对一。相对路径及行号通过外部映射加入**最终上下文**，不是夹进抽取正文。共同采用 o200k token 预算4000和12000；Local的报告、实体、关系及原文全部计数。各表保持实际顺序，统一CSV序列化并增加来源位置，超额时删除尾部完整条目。官方原始上下文与适配后的实际上下文分别保存，不能用原始候选当最终命中。

BM25保留完整标识符及snake/camel词段；hybrid以相同持久化源码向量作cosine排名，与BM25各前20名进行RRF（60，等权）。Basic的最终材料按官方加载文本顺序组织，**不保证向量分数降序**；其MRR描述实际展示顺序。Local源文份额0.5、社区0.15；实体10、关系10；社区层级取实际最大且不超过2。全部参数来自冻结协议，未看结果后调参。

题目与证据由AI研究助手依据源码拟定，并由独立审阅代理核对；提供路径、闭区间行号与hash供人复查，没有独立人类标注或人类评分。下文的逐项需求审查也由研究助手执行。冻结协议中的“人工核对”描述逐项审阅方式，不应据此声称实际已有独立人类评审。

20题包含4个dev和16个test，Q19没有gold，不进入Recall/MRR分母。Q20的运行时目标应保持未知；本轮纯检索不评模型是否正确拒答。F01/F02另做4组×2题、每题一次生成，4000-token初始证据、同模型同提示词，不向编辑模型提供验收测试或额外源码搜索。补丁必须先做范围与安全检查，再放到独立干净副本运行冻结验收及59项原版回归。不能把两题算成可靠的行业成功率。

## 调用、故障和时间怎样记

实际模型为用户选定的one.fullstar.tech `gpt-5.6-luna`和官方OpenAI `text-embedding-3-large`（3072维）。代理内部模型映射不能独立验证。模型请求、失败、缓存及provider usage单独记账；生成费用未知，embedding金额按官方单价估算，并非核对过的账单。

生成请求仍写2048输出token，但上游可能忽略。首次完整索引第14条完整回复报告2278输出token、可见正文1220，因此被最初的本地校验拒绝。按照用户事先接受该风险及继续完整评测的授权，离线确认完整性后保留原回复、记录超额并复用；没有重发。原失败快照和事件保留。后续完整回复也保留真实usage，不截断成伪造的合规输出。时间、物理尝试次数和embedding累计$1边界仍有效。生成回复仍最多读取2MiB；开始向量阶段前，发现32个3072维float向量的格式化JSON可能约2.82MB，因此仅将embedding回复接收上限改为4MiB。请求正文、模型参数及batch不变，不截断或接纳部分回复；新worker记录实际代码hash和回复字节数，已运行的控制器保留原执行版本。该小型传输修复无需重发。

第159条在60秒后超时，没有完整回复；2026-10-13 00:24 UTC用户明确接受可能重复计费并允许只重试它一次。158份成功缓存逐条复验后，第160条以完全相同请求返回成功。当时恢复窗口为00:25:50–02:25:50 UTC。索引完成后，查询执行两次被自动审批拒绝，没有发请求；该窗口到期。用户于02:35:52 UTC重新明确确认18条剩余查询向量及最多8次功能生成。新评测窗口从实际检索启动02:41:34至04:41:34 UTC；查询在02:41:45结束，功能生成在02:46:20结束。原起始时间、历史请求和用量保留，累计embedding $1及请求总上限不重置。此批没有重试或修补。

索引过程计时与接口安装、调试、审批等待分开。正式停止／恢复的间隔不算算法索引耗时；请求延迟、实际workflow时间与从首次启动到结束的经历时间分别给出。检索计时是一轮热缓存计算，查询网络embedding另计，不能称冷启动生产服务延迟。BM25教学实现每次查询都重新分词和计频，hybrid还用Python计算cosine；没有预建高效倒排索引。因此这些耗时只描述本次脚本，不能用于宣称某一产品路线更快。按用户要求不做资源监控：**峰值内存未测**，官方stats里的内存0只是关闭采样后的占位值。

Leiden种子固定20261012；恢复进程启动前也设置PYTHONHASHSEED。第一次正式进程仅在Python启动后设置了该环境变量，未能固定该进程已有的哈希随机种子；不为此重复付费请求，保留并披露差异。模型端未提供经过验证的确定性采样保证。相同原始结果可以精确复算分数，重新调用模型不保证逐字重现。

## 最轻的复算：不用模型

在仓库根目录运行：

```bash
python3 research/pilot/verify.py
python3 research/pilot/verify_results.py
python3 research/pilot/score_results.py --check
python3 research/pilot/verify_feature_results.py
python3 -m unittest discover -s tests
python3 -m unittest discover -s research/pilot/tests
python3 scripts/validate.py
```

验证器逐项检查20×4×2加2×4的唯一完整网格、实际上下文与渲染表一致、源码片段哈希、来源行号，以及评分侧车与实际Sources一致。token精确重数使用原小型tokenizer缓存及 `verify_results.py --tokens`；需要先完成下面的静态输入准备。CI不运行长索引或模型调用。

## 重建运行环境与输入

使用Python3.12。微软源码和Requests快照仅下载到忽略缓存，不执行Requests安装脚本。官方运行时有安装构建步骤；依赖从PyPI取得。完整包版本随环境结果记录。以下准备不调用模型：

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r research/pilot/requirements.txt
.venv/bin/python research/pilot/prepare.py --fetch
.venv/bin/python research/pilot/verify.py --source
.venv/bin/python research/pilot/fetch_runtime.py
uv venv --python 3.12 .cache/graphrag-venv
uv pip install --python .cache/graphrag-venv/bin/python -r research/pilot/runtime-requirements.txt
```

再安装固定源码的8个包。这里的版本路径与[来源清单](../microsoft-version.json)一致：

```bash
MS_ROOT=.cache/ms-graphrag/graphrag-5faaaf4f5685fa2056fa8c3bf9342cb089f2942f
uv pip install --python .cache/graphrag-venv/bin/python --no-deps \
  "$MS_ROOT/packages/graphrag" "$MS_ROOT/packages/graphrag-cache" \
  "$MS_ROOT/packages/graphrag-chunking" "$MS_ROOT/packages/graphrag-common" \
  "$MS_ROOT/packages/graphrag-input" "$MS_ROOT/packages/graphrag-llm" \
  "$MS_ROOT/packages/graphrag-storage" "$MS_ROOT/packages/graphrag-vectors"
```

## 有成本的重跑

运行前须自行确认服务权限、预算和[仓库外凭据](credentials.md)。仓库已保存探测、中断、完整索引、检索和功能尝试记录。阅读这些记录无需发请求。运行器固定独立目录并拒绝重复启动，已运行的目录不能直接覆盖。成功缓存只按完整请求参数／endpoint或精确embedding输入复用；失败或结果不明不会自动重试。

在全新clone中重跑时，历史探针缓存可以不存在，先前用量从0记起。将新结果放到独立目录，避免覆盖已发布结果；下列环境变量只影响结果输出，核验已发布结果时不要设置它。

```bash
export CODE_RAG_RESULTS_DIR=.cache/pilot/reproduction-results
PYTHONHASHSEED=20261012 .cache/graphrag-venv/bin/python research/pilot/full_index.py prepare
PYTHONHASHSEED=20261012 .cache/graphrag-venv/bin/python research/pilot/full_index.py index
PYTHONHASHSEED=20261012 .cache/graphrag-venv/bin/python research/pilot/full_retrieve.py --execute
.cache/graphrag-venv/bin/python research/pilot/verify_results.py --tokens
.cache/graphrag-venv/bin/python research/pilot/score_results.py --tokens
PYTHONHASHSEED=20261012 .cache/graphrag-venv/bin/python research/pilot/full_features.py --generate
```

编辑输出先复核，再应用到每题每组独立副本；[冻结测试运行器](run_tests.py)提供断网验收入口。原始补丁和应用失败诊断已公开，因全部补丁损坏没有产生候选测试日志；可以离线核验，不要求再次调用编辑模型。一次失败输出也属于实验结果，不修补后冒充原模型一次成功。

## 解释边界

只有一个较小Python项目，题目由AI研究助手拟定并经独立审阅代理核对，可能与训练材料重合；没有跨仓库泛化证据。默认文档实体图不是AST／符号调用图；本轮没有定制代码实体类型、reranker、agentic搜索、动态调用验证、更新删除实验，也没有“去图但其余相同”的因果消融。4000/12000等预算比较可以约束“是否只多给了上下文”，不能将所有差异归因于图本身。未标成gold的材料是未判定，不一概算噪声。源码证据覆盖不是答案准确率。

## 定性证据复核的预定范围

在实际检索分数生成前，固定选择Q01（定位）、Q07（调用）、Q13（影响）、Q20（动态未知）的4000-token上下文作两位独立审阅代理的定性复核。隐藏方法名并用固定种子20261012打乱编号；上下文结构仍可能暴露方法类型，因此不是完全盲法。核对新增相关原文、未判定材料和关系描述边界；不改gold或主分数，不据四题估计总体噪声率。实际复核按两位代理分工进行，每题由一位评价，不是每题双人一致性评分；标签映射在评价提交后公开：[Q01/Q07审阅](results/qualitative-audit.json)、[Q13/Q20审阅](results/qualitative-fact-review.json)、[映射](results/qualitative-method-key.json)。

## 评测执行补充记录（2026-10-13）

22条查询中4条来自原缓存，新增18条共606个输入token，仅1批OpenAI请求。共享查询向量准备耗时3.590秒；随后检索仅从缓存读取。4000预算下四组测试题平均脚本检索计算分别为31.5／51.2／10.8／14.5毫秒（BM25／hybrid／Basic／Local），单轮热缓存、没有优化的实现，不能当生产吞吐或产品排名。上下文重新序列化耗时另存各题记录。

功能实际8次物理请求、无缓存命中或重试，provider输入41,361、输出18,571 token；7份完整回复超过请求2048输出上限，原样记录。8份均因损坏diff无法应用，未运行候选测试；逐项原文、hash及诊断可用`verify_feature_results.py`离线检查。累计OpenAI估算为206,333 × $0.13/百万 = **$0.02682329**，包含旧探针，不是账单；one.fullstar未估价。所有生成已知usage含索引及功能为输入1,815,315、输出334,812，第159条未知量仍不计为0。

表中后续数字保留**索引完成时**口径，避免把查询和功能成本混入索引成本。没有做独立冷启动BM25／hybrid建库计时，不能据此计算严谨的成本倍数。

## 已完成的正式索引记录（2026-10-13）

默认Standard索引完成：114文本块、639实体、1069关系、84社区和84报告。实体类型为338 EVENT、295 ORGANIZATION、4 PERSON、2 GEO。实体来源关联到101/114块，其余原文仍保留在文本表中；不能据图已生成就声称Local的实体来源分支覆盖全库。

| 成本或检查项 | 实际记录 |
| --- | --- |
| 正式索引生成尝试 | 518：初抽115、补抽114、描述整理205、报告84；含结果不明的159及获准重发160 |
| 正式索引embedding | 46批，provider usage 201,400输入token；此前探针4,327另计 |
| 累计embedding估算 | 205,727 token × $0.13/百万 = $0.02674451；不是核对过的账单 |
| 索引已知生成usage | 输入1,773,954，输出316,241；第159条未知用量不按0估计，生成费用未知 |
| 实际索引workflow累计 | 4,276.704秒，约71.28分钟，含失败工作及恢复后的缓存读取 |
| 诊断／等待停止间隔 | 27,475.088秒，约7.63小时；与算法运行分列 |
| 首次启动至索引完成 | 31,751.888秒，约8.82小时；不能称纯索引计算时间 |
| 输出目录／向量存储 | 12,313,627字节／10,716,130字节；不含模型权重，原缓存与向量不发布 |
| 请求输出限额 | 20份完整回复超过请求的2048 token，原样保留并记录 |
| 抽取格式诊断 | 228份成功抽取正文中213份以预期结束标记结尾；其余15份由官方解析路径继续处理，不能据此证明抽取完整；未补写或重发 |
| 峰值内存 | 未测，不能将停用采样后的0占位值当真 |

数值可从[完整账本](results/execution.json)、[图表导出](results/index-summary.json)和[格式诊断](results/extraction-format-diagnostics.json)检查。实体／关系／报告是模型产物，不是已验证的程序事实。图数据中的类型、名字和描述均保持实际输出，不人工修图。

对15份异常结束串的缓存检查：4份为`<|>COMPLETE|>`，11份为`<|>COMPLETE<|>`，保存的统一终止状态均为`stop`。涉及9块；将原初抽与补抽按官方代码直接拼接后，官方解析器仍产出69条实体、103条关系记录。这些是合并前记录数，不是最终图规模。全114块解析出1160实体记录、1408关系记录，其中197条关系因最后字段不能转为浮点数，按官方代码采用权重1.0；其中53次出现在这9块，另外144次出现在其余105块，不能全归因于上述15份异常。没有修改回复、提示词、解析器或最终图。它说明格式异常可能改变实际图权重，而不是证明这些块信息完整或发生传输截断。后续效果只能归于本次模型服务、提示词和官方解析器的实际组合。详见[解析诊断](results/extraction-parser-diagnostics.json)；保有原缓存时可离线运行 `research/pilot/inspect_extraction_format.py` 复算。
