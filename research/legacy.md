# 旧版去了哪里

当前对象为 **Microsoft GraphRAG 对代码索引／上下文检索的价值**，按精确定位、调用追踪、修改影响和 feature 四项开发任务组织。最早版本实现的是 BM25／向量检索与自制代码结构图扩展，并没有运行 Microsoft GraphRAG。因此，旧版成绩不能回答当前问题，不再作为正文的证据。

旧版完整保留于提交 [`ce5d4c6cc78253fd7d70b27fb71e467ac9d38141`](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141)：

- [旧报告](https://github.com/Xingqi-Chen/code-rag-field-guide/blob/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/docs/report.md)
- [旧题集和协议](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/benchmark)
- [旧结果](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/results)、[旧日志](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/logs)、[旧脚本](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/scripts)

当前版本删除旧 benchmark、results、实验日志、语料许可证副本、旧实验与下载脚本、重型依赖锁定、对应测试和旧结构图配图，并重写报告、README、归因及发布检查。原创小店代码仍用作新报告的教学输入；它不是评测集，也不是微软系统的实测输出。

这是阅读范围的修订，不是隐藏负结果。旧结果仍按原协议保留在历史提交中，且无论旧图方法输赢，都不能用来评价 Microsoft 实现。本仓库保留正常提交历史，不改写旧提交，不 force push。

中间版本 [`f9f39ee`](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/f9f39ee8a00f5fc38090d91fc2f5f103e2dcd312) 已转向微软文献／源码研究，但较侧重整体架构理解与社区导读。当前版本按开发任务重写主文和四图，补充来源精度、索引新鲜度、官方代码研究线索以及检索／改码分开的验证计划；该中间版本同样保留在历史中。
