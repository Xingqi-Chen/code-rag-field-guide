# 旧版去了哪里

本轮把对象收窄为 **Microsoft GraphRAG 对代码库理解的价值**。旧版实现的是 BM25／向量检索与自制代码结构图扩展，并没有运行 Microsoft GraphRAG。因此，旧版成绩不能回答本轮问题，不再作为新版正文的证据。

旧版完整保留于提交 [`ce5d4c6cc78253fd7d70b27fb71e467ac9d38141`](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141)：

- [旧报告](https://github.com/Xingqi-Chen/code-rag-field-guide/blob/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/docs/report.md)
- [旧题集和协议](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/benchmark)
- [旧结果](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/results)、[旧日志](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/logs)、[旧脚本](https://github.com/Xingqi-Chen/code-rag-field-guide/tree/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/scripts)

当前版本删除旧 benchmark、results、实验日志、语料许可证副本、旧实验与下载脚本、重型依赖锁定、对应测试和旧结构图配图，并重写报告、README、归因及发布检查。原创小店代码仍用作新报告的教学输入；它不是评测集，也不是微软系统的实测输出。

这是阅读范围的修订，不是隐藏负结果。旧结果仍按原协议保留在历史提交中，且无论旧图方法输赢，都不能用来评价 Microsoft 实现。本仓库保留正常提交历史，不改写旧提交，不 force push。
