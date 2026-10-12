# Microsoft GraphRAG 适合做开发助手的代码索引吗？

一份面向同事分享的中文图文研究，约 10–15 分钟阅读。像查图书馆资料一样：找到主题相关的导读之后，还要确认**具体是哪一页、哪一版、依据是否完整**，才能放心修改。

**[阅读主报告](docs/report.md)** · [四张教学图](docs/figures/README.md) · [源码与直接证据](research/README.md)

聚焦四项任务：**精确找函数／符号、追真实调用／依赖、分析修改影响、辅助实现新增功能（feature）**。整体架构导读仅作辅助背景，不用总结质量推断索引准确或改码成功。

核查对象为 **Microsoft GraphRAG v3.3.0**，截止 **2026-10-12**。固定源码显示：默认文本实体图没有提供程序语义层面的符号身份、调用与影响集合保证，来源定位及修改／删除同步也需额外处理。在本轮公开检索范围内，四类任务的特定价值仍缺足够直接评测证据；这不是断言它无效。

已完成文献、静态源码和图文复核。**微软模型索引、检索评测及改码实验尚未完成。** [小 feature 示例](docs/examples/shop/README.md)是人工教学材料；[真实项目准备包](research/pilot/README.md)已固定 Requests 语料、20题和2个feature，并通过59项本地回归。原版、提示词定制、外接程序图分别讨论。

旧自制代码图实验未测试微软实现，保留于[正常 Git 历史](research/legacy.md)，不作为新版效果证据。

**最新实测：**首次401后，用户更新key并授权续批；一次初抽与两批官方embedding通过当前校验，随后补抽HTTP500而停止。累计3次生成尝试、2批embedding，没有自动重试。[真实记录与未完成边界](research/pilot/probe-result.md)。接口结果不是GraphRAG检索效果证据。

**兼容修复：**Responses JSON/SSE传输适配已完成离线测试；尚未重新请求服务。真实调用入口保持关闭，因为代理可能丢弃请求的2048输出上限，见[修复与下一步边界](research/pilot/probe-result.md#离线传输修复2026-10-12)。

发布快检不需要网络或模型：

```bash
python3 -m unittest discover -s tests
python3 scripts/validate.py
```

[研究过程](research/process.md)记录源码哈希核对、教学代码检查、配图生成与独立复核。CI 只做轻量检查。原创内容适用 [MIT](LICENSE)；第三方来源见 [NOTICE](NOTICE.md)。
