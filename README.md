# Microsoft GraphRAG 能帮我们读代码吗？

一份面向同事分享的中文研究，约 10–15 分钟阅读。把它想成资料整理员：先识别事物与关系，分组写导读，再拿这些材料回答问题。**导读可能帮助理解全局，但图上的关联不等于经程序分析验证的调用。**

**[阅读图文报告](docs/report.md)** · [四张原理图](docs/figures/README.md) · [研究记录与证据](research/README.md)

本轮聚焦 **Microsoft GraphRAG v3.3.0**，核查截止 **2026-10-12**。分别讨论局部代码问答、跨文件流程和整体架构理解。在本轮公开检索范围内，**未检索到足够直接证据**支持它在这些任务上稳定优于强检索方案；这不是断言无人研究，也不是断言方法无效。

已完成文献与固定源码核查、原创教学图，以及[后续试点方案](research/pilot-decision.md)。**未运行 Microsoft GraphRAG 的模型索引或回答实验，未发起付费模型调用。** 所有示意图均标明不是实测输出。

旧版自制代码结构图实验没有测试微软实现，已从当前内容移出，完整保留于[正常 Git 历史](research/legacy.md)。

无需模型和网络的发布快检：

```bash
python3 -m unittest discover -s tests
python3 scripts/validate.py
```

配图生成和只读源码核对方法见[研究过程](research/process.md)。CI 只做轻量检查，不下载模型、不运行长实验。原创内容适用 [MIT](LICENSE)；第三方来源见[许可与归因](NOTICE.md)。
