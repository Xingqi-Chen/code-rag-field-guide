# 完整评测的执行与复算说明

这是主报告的技术附录；结论与汇总只在[主报告](../../docs/report.md)维护。题集、证据和评分协议见[冻结协议](protocol.md)，本轮授权与运行界限见[运行计划](full-run-plan.json)。

**检索与功能阶段尚未完成。** 2026-10-13经明确授权恢复索引，下文尚未执行的阶段描述的是冻结计划，不能读作验收已通过；实际状态以执行记录为准。

## 比较的究竟是什么

固定 Requests 2.32.3 的 41 个源码、测试、文档和配置文件，共114个完整行文本块。四组是 BM25、BM25＋真实 embedding 的 hybrid、Microsoft Basic、Microsoft Local。后两组使用固定 v3.3.0 官方内部上下文 builder；没有调用其回答生成 API。Local 的图由官方 Standard 流程生成，默认实体类型与抽取／摘要／社区提示词不改。

共享输入按完整行预切块，微软第二次切块设置1200/0，并实测逐字一对一。相对路径及行号通过外部映射加入**最终上下文**，不是夹进抽取正文。共同采用 o200k token 预算4000和12000；Local的报告、实体、关系及原文全部计数。各表保持实际顺序，统一CSV序列化并增加来源位置，超额时删除尾部完整条目。官方原始上下文与适配后的实际上下文分别保存，不能用原始候选当最终命中。

BM25保留完整标识符及snake/camel词段；hybrid以相同持久化源码向量作cosine排名，与BM25各前20名进行RRF（60，等权）。Basic的最终材料按官方加载文本顺序组织，**不保证向量分数降序**；其MRR描述实际展示顺序。Local源文份额0.5、社区0.15；实体10、关系10；社区层级取实际最大且不超过2。全部参数来自冻结协议，未看结果后调参。

20题包含4个dev和16个test，Q19没有gold，不进入Recall/MRR分母。Q20的运行时目标应保持未知；本轮纯检索不评模型是否正确拒答。F01/F02另做4组×2题、每题一次生成，4000-token初始证据、同模型同提示词，不向编辑模型提供验收测试或额外源码搜索。补丁必须先做范围与安全检查，再放到独立干净副本运行冻结验收及59项原版回归。不能把两题算成可靠的行业成功率。

## 调用、故障和时间怎样记

实际模型为用户选定的one.fullstar.tech `gpt-5.6-luna`和官方OpenAI `text-embedding-3-large`（3072维）。代理内部模型映射不能独立验证。模型请求、失败、缓存及provider usage单独记账；生成费用未知，embedding金额按官方单价估算，并非核对过的账单。

生成请求仍写2048输出token，但上游可能忽略。首次完整索引第14条完整回复报告2278输出token、可见正文1220，因此被最初的本地校验拒绝。按照用户事先接受该风险及继续完整评测的授权，离线确认完整性后保留原回复、记录超额并复用；没有重发。原失败快照和事件保留。后续完整回复也保留真实usage，不截断成伪造的合规输出。时间、2MiB响应大小、物理尝试次数和embedding累计$1边界仍有效。

第159条在60秒后超时，没有完整回复；2026-10-13 00:24 UTC用户明确接受可能重复计费并允许只重试它一次。158份成功缓存逐条复验后，第160条以完全相同请求返回成功。新的恢复窗口为00:25:50–02:25:50 UTC，检索和功能阶段共用这个窗口；原起始时间、历史请求和用量保留，累计embedding $1及请求总上限不重置。

索引过程计时与接口安装、调试、审批等待分开。正式停止／恢复的间隔不算算法索引耗时；请求延迟、实际workflow时间与从首次启动到结束的经历时间分别给出。检索计时是一轮热缓存计算，查询网络embedding另计，不能称冷启动生产服务延迟。BM25教学实现每次查询都重新分词和计频，hybrid还用Python计算cosine；没有预建高效倒排索引。因此这些耗时只描述本次脚本，不能用于宣称某一产品路线更快。按用户要求不做资源监控：**峰值内存未测**，官方stats里的内存0只是关闭采样后的占位值。

Leiden种子固定20261012；恢复进程启动前也设置PYTHONHASHSEED。第一次正式进程仅在Python启动后设置了该环境变量，未能固定该进程已有的哈希随机种子；不为此重复付费请求，保留并披露差异。模型端未提供经过验证的确定性采样保证。相同原始结果可以精确复算分数，重新调用模型不保证逐字重现。

## 最轻的复算：不用模型

结果发布后，在仓库根目录运行：

```bash
python3 research/pilot/verify.py
python3 research/pilot/verify_results.py
python3 research/pilot/score_results.py --check
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

运行前须自行确认服务权限、预算和[仓库外凭据](credentials.md)。仓库现有探测与中断记录，完整结果尚未生成；阅读这些记录无需发请求。运行器固定独立目录并拒绝重复启动，已运行的目录不能直接覆盖。成功缓存只按完整请求参数／endpoint或精确embedding输入复用；失败或结果不明不会自动重试。

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

编辑输出先复核，再应用到每题每组独立副本；[冻结测试运行器](run_tests.py)提供断网验收入口。补丁和测试记录尚未生成；完成并公开后可以离线复算，不要求再次调用编辑模型。一次失败输出也属于实验结果，不修补后冒充原模型一次成功。

## 解释边界

只有一个较小Python项目，题目由人工设计，可能与训练材料重合；没有跨仓库泛化证据。默认文档实体图不是AST／符号调用图；本轮没有定制代码实体类型、reranker、agentic搜索、动态调用验证、更新删除实验，也没有“去图但其余相同”的因果消融。4000/12000等预算比较可以约束“是否只多给了上下文”，不能将所有差异归因于图本身。未标成gold的材料是未判定，不一概算噪声。源码证据覆盖不是答案准确率。
