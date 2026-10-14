# Microsoft GraphRAG 适合做开发助手的代码索引吗？

把代码仓库想成图书馆：关键词搜索查原文，向量检索按意思找段落，Microsoft GraphRAG 先制作“事物卡片”和关系导读。导读能提供线索；真正改代码，还要找到**具体哪一页、哪个版本、哪些调用者和测试**。文档实体图与程序的符号／调用图是两种东西，不能因为都有“图”，就认定能解决相同问题。

**[阅读中文主报告](docs/report.md)** · [通俗原理与架构图](docs/graphrag-explained.md) · [实验方法与复算](research/pilot/full-run.md) · [一手来源导航](research/README.md)

固定 **Microsoft GraphRAG v3.3.0**；文献检索截止 **2026-10-12**，实验完成于 **2026-10-14**。本次重点验证微软实现；旧自制代码结构图实验保留在[Git历史](research/legacy.md)，不混入下表。

**代码提示词＋实体类型配置的 Local 在本次覆盖更高，但整体证据覆盖仍落后于 hybrid。** 同一 Requests 快照、冻结问题和评分规则下，结果如下。各列是整个上下文的 token 上限，百分比是必要源码证据覆盖率，**不是回答正确率**。

| 方法 | 4000 | 8000 | 12000 | 16000 |
| --- | ---: | ---: | ---: | ---: |
| BM25关键词 | 35.3% | 43.7% | 64.3% | 69.3% |
| 关键词＋真实向量hybrid | **42.9%** | **56.3%** | **71.0%** | **77.9%** |
| Microsoft Basic向量 | 35.8% | 55.8% | 57.4% | 57.4% |
| Local：默认抽取 | 5.6% | 21.0% | 21.0% | 23.2% |
| Local：代码提示词＋实体类型 | 19.0% | 42.2% | 53.8% | 55.4% |

主分母是15道可评分测试题；另1道无实现负例不计召回，4道开发题单列。实际取回的原文须覆盖一段预标证据至少80%的行才算命中，再按题平均；严格100%行口径结果相同。[400份上下文的合并分数](research/pilot/results/code-prompt/scores.json)与[复算汇总](research/pilot/results/code-prompt/analysis.json)公开。

**找全与排前有不同结果。** 16000档，代码配置的 Local 首条相关源码排序更好：MRR为0.619、前5块证据召回为53.8%，均高于hybrid的0.528、48.4%；但完整上下文只覆盖55.4%，hybrid为77.9%。相同上限也不等于相同实际源码量：两者按16道test平均的源码量约7398与14666 token。图有补充线索的价值，尚不足以证明可以替换基础检索。

**改善与失败同时存在。** Q07调用链的覆盖从默认Local的0升至60%，命中Session中段，仍缺公开API入口；Q01虽然有更精确的方法卡片，四档仍没交回字典实现，覆盖为0。[固定案例追踪](research/pilot/results/code-prompt/fixed-local-review.json)把“抽到了”“进了图”“进了检索材料”分开核对。

**成本不小，结论范围也有限。** 新配置有1628实体、2891关系和372份报告；1347次实际生成尝试、103批新embedding，索引输出31.65 MB。已记录请求耗时合计约206.4分钟，另有一次缺失耗时；跨中断的全程约13.49小时，不能当作纯计算时间。生成费用未知，内存峰值未测。默认版与新配置的超时、恢复规则也不同，且新配置是在看过旧失败之后设计；这是探索性比较，不能把全部改善归因于提示词。[完整成本、恢复及边界](research/pilot/results/code-prompt/README.md)

**适合尝试的场景：**需要理解分散概念、寻找额外测试线索，且允许按commit低频生成并核对导读。**不能仅靠它的场景：**唯一符号定位、完整调用者集合、运行时动态目标、频繁改删同步。建议先做好关键词＋真实向量基线、来源位置和版本，再让图证明能补到遗漏；外接AST／符号图应另行评测。

默认图另做了6题Global真实回答对照：能整理职责和测试主题，也有错误方法名和无效引用；输入量是BM25的7.86倍，并非等预算。两个功能任务共8份单轮补丁均因diff损坏无法应用，未进入测试。新代码配置**未重跑Global、生成回答或功能修改**，不宣称端到端准确率。[Global原始回答](research/pilot/results/global) · [功能尝试与限制](research/pilot/full-run.md)

实验由用户指定Mac mini编排，模型来自获授权的远端服务，**不是本地权重推理**。主要局限是一个较小Python仓库、AI拟题和AI复核、没有独立人类评分；没有等实际源码量／随机邻居消融，不能概括整个行业。运行时JSON格式修复、未知用量和中断均保留，不以索引成功或图更大作为效果证据。

发布快检不需要网络、凭据或模型：

```bash
python3 -m unittest discover -s tests
python3 -m unittest discover -s research/pilot/tests
python3 research/pilot/verify_code_prompt_completed.py
python3 research/pilot/evaluate_code_prompt.py check
python3 research/pilot/analyze_code_prompt.py --check
python3 research/pilot/complete_code_prompt_evaluation.py --check
python3 scripts/validate.py
```

完整检查见[CI](.github/workflows/verify.yml)。原创内容适用[MIT](LICENSE)，第三方片段见[许可与归因](NOTICE.md)。[四张图与小店示例](docs/figures/README.md)是教学材料，不是微软输出。[研究过程](research/process.md)保留真实提交、原始结果和独立复核。
