# 完整评测的执行与复算说明

这是主报告的技术附录；结论与汇总只在[主报告](../../docs/report.md)维护。题集、证据和评分协议见[冻结协议](protocol.md)，本轮授权与运行界限见[运行计划](full-run-plan.json)。

**完整索引、首轮168份上下文（含8份功能材料）和8次单轮功能生成已完成；后续离线新增160份检索上下文。** 结果与来源通过离线验证；8份补丁均在原样应用检查中损坏，功能验收和回归未执行，不把未测当测试0分。效果解释统一见[主报告](../../docs/report.md)，逐题见[分数](results/scores.json)、[检索材料](results/contexts)、[功能记录](results/features)；[离线补测结果](results/budget-supplement)与[轻量独立复核](results/budget-supplement/review.json)另存。实际索引见[执行账本](results/execution.json)与[规模记录](results/index-summary.json)，发布前[独立数值与公平性复核](results/evaluation-review.json)未发现阻断问题。

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

只有一个较小Python项目，题目由AI研究助手拟定并经独立审阅代理核对，可能与训练材料重合；没有跨仓库泛化证据。默认文档实体图不是AST／符号调用图；本轮没有定制代码实体类型、reranker、agentic搜索、动态调用验证、更新删除实验，也没有“去图但其余相同”的因果消融。4000／8000／12000／16000预算比较可以约束“是否只多给了上下文”，不能将所有差异归因于图本身。未标成gold的材料是未判定，不一概算噪声。源码证据覆盖不是答案准确率。

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

## 离线预算补测：8000与16000（2026-10-13）

用户明确要求追加检索预算比较。首轮4000／12000结果逐字保留，只新增20题×4方法×2档＝160份；现在检索320份，加首轮功能8份，共328份。功能没有重做。先提交[补测计划](budget-supplement-plan.json)，再以598a3b2版本入口于04:00:43–04:00:51 UTC执行；元数据写入前时长8.527秒、[真实运行日志](results/budget-supplement/run.log)收尾8.551秒，仅为重组上下文的过程，不含后续评分、审阅和报告编辑。[补测账本及原材料](results/budget-supplement/retrieval.json)记录原文件hash、源码向量hash、20个查询向量hash、原付费账本前后相同hash及运行脚本hash。

**新增生成0、embedding0、重建图0，费用不变。** 独立入口只读本机现有图表／向量，查询接口仅作精确字符串到缓存向量的内存查表，cache miss立即失败，没有实例化付费Runtime或provider adapter；Python网络审计钩子拒绝连接/DNS/HTTP调用，实际触发0次。此前账本仍为索引生成518、功能生成8、embedding47批、累计206,333输入token，未重置或增加。原图结束标记及权重解析异常照旧，不重抽、不人工修图。

补测只改预算，其他参数保持：Basic `k=10`，hybrid两路各前20／RRF60，Local来源0.5／社区0.15／实体关系余下0.35、实体10、关系10、层级2。v3.3.0的`LocalSearchDefaults`正常配置确为0.5／0.15；`LocalSearchMixedContext.build_context`函数签名的社区默认值另为0.25，本实验始终显式传正常配置0.15，未混用。源码、图摘要、表头和来源位置共同计入最终o200k预算。

平均必要证据覆盖的主分母仍为15道可评分test；实际上下文量按16道test平均。逐题、dev、Recall和MRR在[补测分数](results/budget-supplement/scores.json)，四档精确数值在[预算分析](results/budget-supplement/budget-analysis.json)。表格仅为主报告所用数值的精确复核入口：

| 方法 | 上限 | 实际平均token | 源码原文平均token | 实际总量／上限 |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 4000 | 3566.6875 | 3449.9375 | 89.17% |
| BM25 | 8000 | 7240.4375 | 7010.6875 | 90.51% |
| BM25 | 12000 | 11448.6250 | 11087.5000 | 95.41% |
| BM25 | 16000 | 15441.3125 | 14947.3125 | 96.51% |
| hybrid | 4000 | 3625.8750 | 3479.0625 | 90.65% |
| hybrid | 8000 | 7429.3125 | 7134.4375 | 92.87% |
| hybrid | 12000 | 11267.5625 | 10831.8125 | 93.90% |
| hybrid | 16000 | 15242.3750 | 14665.9375 | 95.26% |
| Basic | 4000 | 3592.5000 | 3454.7500 | 89.81% |
| Basic | 8000 | 7372.6875 | 7059.4375 | 92.16% |
| Basic | 12000 | 10548.8750 | 10059.9375 | 87.91% |
| Basic | 16000 | 10941.2500 | 10433.5625 | 68.38% |
| Local | 4000 | 2648.2500 | 1250.6250 | 66.21% |
| Local | 8000 | 6025.9375 | 3542.1250 | 75.32% |
| Local | 12000 | 10272.2500 | 5891.6875 | 85.60% |
| Local | 16000 | 11646.5000 | 7214.3125 | 72.79% |

Local各表的份额分别传给构建器，剩余额度不会在表之间自动重分配。完整条目放不下就停；候选数量和排序还会限制能放入的内容。Basic在16000档全部装下10块候选，不能用其平台期断言所有dense检索已经到顶。Local的32份新增test上下文没有被统一适配器额外删尾行。不同阶段查询缓存读取方式不同，本次计时不能直接与首轮磁盘缓存的检索延迟比较。

### 重叠、未判定材料与噪声的区别

[预定描述指标](budget-supplement-plan.json)新增的是可机械复算的检查量，不改原评分：相同`(path,line)`重复出现的次数／总行出现次数，按题取平均，衡量切块交叠；另外检查同一text-unit ID重复，全部为0。这里不衡量不同表之间的语义重复。四档test平均源码行重叠率如下：

| 方法 | 4000 | 8000 | 12000 | 16000 |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 1.55% | 1.70% | 2.29% | 2.36% |
| hybrid | 0.72% | 1.68% | 2.12% | 2.10% |
| Basic | 1.48% | 1.95% | 2.18% | 2.23% |
| Local | 0.00% | 1.17% | 1.22% | 1.47% |

每题还计算取回的去重源码行中，有多少落在冻结必要证据段之外。这个比例在本批很高（约97.7%–99.3%），因为gold只圈必要锚点，而每块接近1200 token；它包括背景、测试、说明、空行及可能无关材料。**该比例不是噪声率，也不是Precision的反面，不能按100%减覆盖率推算噪声。** Q19没有gold，此项聚合排除它。没有新增全面相关性标注，所以只通过Q01/Q07/Q13/Q20的固定案例说明遗漏和旁支，不估总体噪声。

### 离线复算与本机缓存重放

公开仓库可以直接复算，不需要模型或向量缓存：

```bash
python3 research/pilot/score_budget_supplement.py --check
```

加`--tokens`会重新数实际上下文token，需要此前安装的tiktoken与已校验的小词表缓存。评分入口会验证原168份及新增160份，原分数逐项一致，新增唯一网格、源码hash、来源行号及全表渲染一致，再复算新分数、重叠及未判定量。轻量CI执行不带`--tokens`的版本。

**只有保有这台Mac原始索引和查询向量缓存时，重新组织新预算上下文才可完全离线。** 全新clone没有公开的向量库，不能把“免费复算分数”误说成“无需缓存也能重建原图”。已发布目录拒绝覆盖；若持有完整缓存且确需重放，把新输出定向到独立位置：

```bash
export CODE_RAG_SUPPLEMENT_DIR=.cache/pilot/replayed-budget-supplement
PYTHONHASHSEED=20261012 PYTHONDONTWRITEBYTECODE=1 \
  .cache/graphrag-venv/bin/python research/pilot/supplement_budgets.py --execute
.cache/graphrag-venv/bin/python research/pilot/score_budget_supplement.py --tokens
```

该输出目录选项在本次实际运行后补入，不改变已记录的执行源码与脚本hash，也未因此重跑。补测结果属于已看过首轮结果后的预算敏感性分析；题、gold和旧结果不变，不将它包装成新的独立泛化评测。


## Global：六题真实回答补充实验

本节是2026-10-13新增的探索性回答评测，与前面20题纯检索和两项补丁实验分别记录。用户明确允许新增模型调用后，在执行前提交了[六题](global-questions.json)、[逐项标准与源码锚点](global-gold.json)、[协议](global-plan.json)、[离线预算核算](results/global/preflight.json)及执行器，冻结提交为 `b3a1201`。问题是Q01定位、Q07调用、Q13影响、原F02改写成只做规划，以及两道新增认证架构／扩展题G01、G02。此前检索结果已知，因此这是有目的选题的后续探索，不能说是从未看过结果的全新盲测；新增题没有用于改索引或调参。

固定同一Requests快照、同一微软v3.3.0运行时及原有索引。按官方 `read_indexer_reports(..., community_level=2)` 选择规则得到84份报告；这里的level是过滤／归并参数，不应误写成84份全都恰好位于第2层。使用报告全文而非短summary，固定seed 20261012，关闭动态社区选择和外部常识补充；报告中的已有抽取异常原样保留。没有重建索引、修图或调用embedding，先前OpenAI累计额度与用量不变。

调用的是实际安装的官方 `GlobalCommunityContext` 与 `GlobalSearch.search`。每题先对7批社区报告分别发起模型map，再由官方解析分数、过滤0分条目、排序并构造reduce，最后真实调用模型汇总。若全部map为0分，官方可直接返回固定拒答、无需reduce。不是只取社区摘要或在本地伪造map输出。[固定官方Global实现](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/global_search/search.py)与[报告分批实现](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/context_builder/community_context.py)本次于2026-10-13通过已缓存固定源码核对，未引入截止日后的新版本或文献。

预算需分三层看：每个map批次名义上限12000，7批实际材料合计**78,250 o200k token／题**；reduce筛选材料上限12000；BM25对照只在相同114块上检索一次、直接源码材料上限12000。两组的共同用户问题、同一 `gpt-5.6-luna` 模型标识、2048请求输出上限相同，但系统提示词、调用数量与总阅读量不同，不能称为等总预算或单独证明图的因果优势。本轮统一用BM25作六题对照，以保持同一种检索器且无需新增向量请求；没有新增hybrid、Basic或Local的回答生成对照。每题只尝试一次，固定seed只约束社区分批顺序，不保证远端生成逐字确定。map/reduce的1000／2000是官方提示中的**词数**要求，不是服务端token硬限制。服务此前有忽略输出上限的情况，本轮保留完整响应、真实usage和超限标记，不截掉超出的结果。

离线核算为最多6×(7 map+1 reduce+1 BM25)=54次；执行硬上限60次、3600秒、每次worker60秒、单请求内容16000 token、整批内容864000 token、响应2 MiB、并发1、零自动重试。任何新传输／适配失败或未知结果终止整批，不重发。执行时只读取原有专用Fullstar凭据；不新增账户、权限或订阅，不计算Fullstar价格。

### 实现适配与评分含义

官方固定版本同时在 `GlobalSearch.__init__` 和 `_map_response_single_batch` 传入 `response_format_json_object`，按默认JSON开关使用会造成重复关键字。执行器使用 `json_mode=False` 避开重复，但官方map调用仍显式要求JSON；沿用已验证的Responses传输，JSON形状由原官方提示要求和解析器处理，没有加入新schema约束。reduce的官方流式接口接收到由一份完整、已核验响应构成的单块异步流。上述适配不改官方提示文本、社区分批、map解析、重点筛选或reduce排序。[执行器](global_experiment.py)与[无网络接口检查](results/global/offline-interface-check.json)公开；独立复核在执行前修复了普通适配异常被官方吞掉后继续请求的缺口。

原始请求只保存公开语料、官方提示和模型可见回答，不保存密钥或私有推理。官方prompt计数没有包含全部用户消息和服务端输出开销，所以总账以逐次provider usage为准，同时保留本地正文token计数；不能只报reduce的上下文大小。社区报告编号是导读出处，不是源码行号；评分分别核查回答内容、正确源码定位、来源支撑、遗漏和无依据断言。每条冻结要求取0／0.5／1，按题归一化，精确题与全局题分别呈现；这是独立AI审阅的必要要点覆盖，不是人类验证的准确率，也不混入原有Recall表。F02这里只评价规划，没有执行或验证新的补丁。

### 复算与重新执行

公开结果的算术及来源完整性可在全新clone里离线核验，不需要任何模型或私有缓存：

```bash
python3 research/pilot/verify_global.py --check
```

该命令校验冻结文件、map与BM25上下文、全部逐次请求／响应、两组共同问题、上限、usage和人工可检查的AI评分，再重算逐题和分组汇总。本机另以 `--check --tokens` 重数全部请求正文、可见输出、map批次与reduce／BM25材料；该可选检查需要已缓存的tokenizer，CI不下载模型。它能验证评分算术与记录一致，不能自动证明评分判断正确。原始数据放在[Global目录](results/global)，此前所有实验文件保持不变。

以下是**实际执行过的顺序**，不是让读者直接覆盖已发布结果的命令：

```bash
# 在既有固定索引缓存及已安装运行时上，先离线准备，再提交冻结材料
PYTHONDONTWRITEBYTECODE=1 .cache/graphrag-venv/bin/python research/pilot/global_experiment.py prepare
# 获得本轮模型调用授权及执行审批后，仅运行一次
PYTHONHASHSEED=20261012 PYTHONDONTWRITEBYTECODE=1 .cache/graphrag-venv/bin/python research/pilot/global_experiment.py execute
```

prepare遇到现有Global结果目录会拒绝覆盖；execute还需要本机未公开的固定parquet缓存，并且遇到已存在的专用运行目录拒绝重启。新clone可复算已公开结果；重新发模型调用则必须在单独研究副本中准备同一版本索引、重新冻结及授权，不能假称仅clone就能逐字重现具有随机性的远端回答。执行阶段也核对了旧索引和旧结果哈希，确保没有回写。


### 实际执行记账

执行从2026-10-13 04:24:08 UTC至04:33:52 UTC，控制器共584.54秒。54次请求全部完成：42 map、6 reduce、6 BM25回答；无失败、重试、补问、索引重建或新embedding。模型可见输入正文共606,476个o200k token；服务报告输入694,712、输出49,786 token。provider计数比纯正文多，不能用正文替代账本；本轮不估算Fullstar费用。

| 调用阶段 | 次数 | provider输入token | provider输出token | 请求监督时间合计 |
| --- | ---: | ---: | ---: | ---: |
| Global map | 42 | 580,261 | 32,206 | 401.14秒 |
| Global reduce | 6 | 36,055 | 7,206 | 99.09秒 |
| BM25单轮回答 | 6 | 78,396 | 10,374 | 83.60秒 |

Global共616,316输入／39,412输出，BM25共78,396输入／10,374输出。Global输入约为BM25的7.86倍；这不是按相同总计算费用比较的实验。三次BM25回答的provider输出分别2357、2236、2396，超过请求2048上限；其可见正文均未超2048。完整响应与usage均保留，没有重复生成或删去超限样本。Global答案中的报告编号已逐一对照输入ID；G02答案引用的Reports(88)不在84份输入报告ID集合；这是需保留的引用失败，不能通过更改答案来修正。


### 独立回答审阅结果

四道精确／规划题按题平均，Global为52.5%，BM25为81.25%；两道全局认证题为45%与65%。逐题分数和错误分别见[精确／规划审阅](results/global/review-precise.json)、[全局审阅](results/global/review-global.json)，算术见[scores.json](results/global/scores.json)。题目要点数量不同，因此组平均是每题归一化后平均，不用总得分直接除总要点代替。额外错误与支持不足不会被覆盖率这一数值自动扣除；必须同时阅读审阅列项，不能把它称为完整回答准确率。

Global在F02计划中的要求覆盖较完整，但很多要求来自题目本身；不能归因于图或声称新功能已正确实现。全局两题都围绕认证，本轮只比较一次回答；两位审阅者分别负责两组题，每题一位审阅者、两个方法，没有每题双评或评阅者一致性统计。未新增生成模型裁判调用。审阅静态源码支持检查，不运行被回答提及的HTTP测试。
