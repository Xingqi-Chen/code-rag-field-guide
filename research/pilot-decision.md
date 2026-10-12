# 必要验证计划已落到 Requests 准备包

日期：2026-10-12。**本轮完成真实项目选择、固定语料、题集/协议冻结及受控本地测试；仍未运行微软模型索引、检索评测或代码生成。**

[阅读准备说明、规模与下一步批准项](pilot/README.md)。技术协议、题目、证据、配置模板、准备脚本和实际日志统一放在 `research/pilot/`，不在主报告重复展开。

第一阶段在 Requests v2.32.3 固定提交上，对照普通hybrid与Microsoft Basic/Local的代码证据检索；第二阶段再用相同编辑器做两个小feature，分别检查检索和改码。项目确被官方SWE-bench采用，但本次自建任务不是官方榜单复现。

已选 one.fullstar.tech `gpt-5.6-luna` 和 OpenAI官方 `text-embedding-3-large`（共享3072维）。[8块兼容性探测](pilot/probe.md)已提出具体请求／token／超时／重试边界及OpenAI金额上限，已获准执行一次，首个生成请求401后停止，未发出embedding请求，见[真实记录](pilot/probe-result.md)。完成准备不代表微软依赖、服务兼容性或完整运行适配器已通过验证；没有实际检索效果数字。探测后再据实制定完整索引预算。
