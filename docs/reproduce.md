# 复现实验

## 只复算已公开结果：无需模型或网络

```bash
python3 scripts/aggregate.py --check
python3 scripts/validate.py
```

`aggregate.py` 从逐题排名、证据分组与块token元数据重新算 Recall/MRR/nDCG/覆盖率，验证冻结后的原始指标，并重算配对bootstrap；不是简单复印汇总表。`validate.py` 独立由冻结行锚重建qrels、核查预算、文件链接和隐私边界。

## 完整本地重跑

在新的克隆目录执行；Python 3.12、Git、uv。模型和源码下载需要网络，其后实验离线运行。不要把语料包安装进虚拟环境，不执行语料的安装/测试脚本。

```bash
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.cache/python"
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt
python3 scripts/fetch_corpora.py
HF_HUB_DISABLE_XET=1 .venv/bin/python scripts/download_model.py
.venv/bin/python scripts/run_experiment.py > logs/experiment.log 2>&1
python3 scripts/aggregate.py
python3 scripts/validate.py
```

此命令会覆盖本地 results 和日志；原始发布结果仍在Git提交里。网络下载、库版本支持与平台轮子可用性取决于上游；原始测量平台是 Apple M4 macOS，其他设备时延不应相同。没有要求调用付费API、安装全局服务或获取新权限。

## 文件导航

- [冻结输入](../benchmark/freeze.json)：协议、问题、语料manifest的SHA-256；对应初始冻结提交 `e87d8e1`。
- [题目与源码证据](../benchmark/questions.md)、[协议](../benchmark/protocol.md)：正负例边界、评分规则及预先固定的超参数。
- [逐题原始结果](../results/raw.jsonl)：450行 = 30题 × 5方法 × 3预算。
- [块元数据](../results/chunks.json)：不含源码正文，含固定URL和token计数；[Requests图](../results/requests-graph.json)、[Click图](../results/click-graph.json)。
- [自动汇总](../results/summary.md)、[机器可读汇总](../results/summary.json)。
- [真实运行日志](../logs/experiment.log)、[环境与分阶段资源](../results/environment.json)、[依赖锁](../requirements.lock.txt)。

## 时延与成本的阅读方法

索引时间不含源码下载和依赖安装。模型加载单列，模型下载不参与检索时延。检索经过预热，每题每阶段3次取中位数；方法总耗时由依赖阶段相加，计入query embedding。图/随机是hybrid共享种子后的额外耗时，不将缓存后图查找几微秒冒充整个系统时延。BM25与dense的排序计入各自阶段。

内存为**同时持有多个索引的整轮进程最大RSS**，不是独立方法内存比较；缓存文件体积采用不同序列化格式，不代表生产向量数据库的空间效率。磁盘源码、模型权重、环境依赖与检索索引应分别理解。没有测增量更新、并发、能耗和生成LLM成本。

## 图提取的具体边界

Python标准库AST解析每个源码文件。定义节点用于确定分块归属；输出图的节点是代码块。

- `same_symbol_next`：同函数/类/模块的相邻块；它本身可能提升长函数覆盖，不能把全部收益归于跨文件调用。
- `static_call`：调用行所在块连接到可解析定义的首块；检索使用双向边，所以也能找部分调用者。名称解析覆盖同模块、导入的名称/模块、`self/cls`同类和可解析基类的方法。
- 不做运行时类型推断、实例赋值数据流、参数对象类型、反射、动态回调、注册表路由、任意多态或外部依赖源码分析。导入按词法作用域解析并保守处理局部遮蔽，但仍不是完整控制流/类型分析，条件绑定与动态分派可能误连；不能当编译器精确调用图。

图只从文本/AST建立，不读取查询和证据标签。Hybrid前半作为种子，一跳邻居按hybrid排名择优；缺邻居时回填hybrid。随机对照从同库全部非种子块抽取，控制槽数而不是度分布；因此它较弱，最重要的对照仍是同预算hybrid。工程实现优先可审阅性，不声称复刻Aider/LocAgent/Sourcegraph。

同符号相邻块是“排除更深定义后，该owner剩余块的顺序相邻”，不保证物理源行号连续。例如模块imports可能与后面的模块级语句相连。它是上下文组织启发式，不是运行时依赖。词法作用域修复后，导入按当前作用域与外层作用域查找，参数、赋值及歧义绑定会阻止退回全局名称；条件分支、装饰器与Python动态绑定仍不能完全解析。
