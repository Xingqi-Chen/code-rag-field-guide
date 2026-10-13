# 失败链与更新语义的离线核验

2026-10-13按用户追加要求进行；解释统一写入[主报告](../../../../docs/report.md)，原理见[通俗说明](../../../../docs/graphrag-explained.md)。这是看过结果后的诊断，不是新保留题实验，不改原gold、评分、图或答案。

## 证据怎样串起来

| 案例 | 原样抽取见证 | 已有图／报告及查询记录 | 可核对的结论 |
| --- | --- | --- | --- |
| Q01字典定位 | 初抽121、补抽122，`structures.py:1–99` | Entity0、138、250；Q01四组16000上下文 | 实现块在库，却没有挂到具体字典实体；Local仍没返回实现 |
| Q07调用链 | 初抽61、补抽62，`api.py:1–109` | Entities0、5；Q07四组16000上下文 | 入口块主要抽出项目和版权作者，未保留所需调用链 |
| Q13类型误述 | 初抽186、补抽187，`test_requests.py:1624–1760` | Entity537→Report35→Q13 map／reduce／答案 | 将输入类型概括成准备后的键类型，错误逐层沿用 |
| G02符号名 | 初抽51、补抽52，`adapters.py:156–310` | Entities133／134→Reports4／50／80→G02 map／reduce／答案 | 序列化方法的双下划线在抽取时已丢失 |
| G02无效出处 | 没有对应抽取错误主张 | Global第53次reduce；所有输入报告及中间引用集合 | Reports(88)不在输入／map引用／reduce材料，最终回复新增 |

[extraction-witnesses.json](extraction-witnesses.json)含四块**原文、8份请求正文及完整可见回复**，从既有本机缓存只读导出，不含凭据、私人路径或模型内部推理。公开复算逐份确认原请求体hash与旧账本一致、请求提示包含`source_text.strip()`、回复hash与此前公开的[格式诊断](../extraction-format-diagnostics.json)一致、源码块hash与[原来源表](../index/text-unit-provenance.json)一致。只挑这些病例作追踪，不估计全库抽取正确率。Requests片段及Microsoft原提示词分别按Apache-2.0及MIT归因，见[NOTICE](../../../../NOTICE.md)。

[embedding-batches.json](embedding-batches.json)只保存既有46批请求的输入hash和对象类别／ID，不保存向量；复算与公开实体描述、报告及源码hash相匹配，并用旧账本累计各类次数、token与请求时间。8个复用源码向量没有新增请求，不包含在106个新源码向量里。

[analysis.json](analysis.json)给出gold对应块与关联实体／关系、四组实际来源、错误传播的具体文本、引用集合、预算表、格式统计和索引阶段计数；完整图及报告仍在[原索引导出](../index)，没有复制成另一套图。[original-manifest.json](original-manifest.json)保存本批开始时479个旧结果／冻结协议文件的hash，复算先验证它们未变。

## 无模型复算

```bash
python3 research/pilot/analyze_failure_chains.py --check
```

仅用Python标准库与公开文件，网络审计钩子拒绝连接。默认不加`--check`只更新本目录`analysis.json`，不会覆盖旧实验。结束标记／解析回退数字重算自之前的解析诊断，并非重新运行“修复后的解析器”；本批没有修标记、重抽、重建、重新embedding或改分。

## 更新处理的小测试

[probe_update_semantics.py](../../probe_update_semantics.py)调用固定v3.3.0的真实`get_delta_docs`和`concat_dataframes`，使用两个假文档的内存表；测试同标题修改、新增、删除和重命名。实际输出见[update-semantics.json](update-semantics.json)。脚本阻断网络，核对执行源码与固定源码文件逐字一致，不初始化索引、模型或向量库。

本机已有对应环境时可复现：

```bash
.cache/graphrag-venv/bin/python research/pilot/probe_update_semantics.py
```

这不是完整更新流水线实验：没有新增时默认loader提前停止来自源码核查；拼接函数另行调用来验证追加行为。没有测真实仓库更新耗时、向量删除、社区重新生成或查询退化。新增文档被处理，不代表任意编辑／删除已可靠同步。依赖未安装时不需要为阅读报告运行微测；CI只做公开证据复算。

## 证据强度与局限

- 直接记录：具体来源遗漏、错误文本传播、无效引用出现阶段、候选和预算、真实请求数与workflow时间，以及四个小表函数行为。
- 有支持但未隔离：默认实体类型与开发任务错配，描述／报告压缩、候选路径及源码份额共同影响结果。
- 待消融：改提示词、修格式、增加源码份额或候选、外接程序图、换模型／仓库能改善多少。没有因果百分比或新增准确率。

原Gold偏重必要源码证据；单仓库、AI选题／审阅、非盲的后续题、远端服务和传输适配均保留为限制。最后答案错误不全来自图：已有BM25回答也误读了给定源码。核验日志与独立审阅在本目录保留，解释不另写一份重复报告。
