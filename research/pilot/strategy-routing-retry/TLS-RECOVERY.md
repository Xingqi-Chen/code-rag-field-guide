# 重试中的 TLS 停止与人工续跑

隔离重试首先完成 Q08；Q10 primer 也成功。2026-10-14 06:41:43 UTC，Q10 后续 embedding 的 event12 被记录为 `transport_security_error`，原有全局停止规则生效。只有固定错误类别，没有原始 HTTP 回复或具体 SSL reason；用量保持未知，该预留和13个输入token继续计数。

随后使用同一 certifi CA、开启 hostname 与证书校验，对 `api.openai.com:443` 做三次纯 TLS 握手，全部通过；没有 HTTP、凭据或模型调用。详情见 [停止快照与 TLS 检查](transport-stop.json)。后来的握手通过不能解释当时的原因，也不能证明当时服务端没有处理请求。

在用户已授权“调查原因并重试六题”的范围内，经独立复核，只允许一次绑定 event12 的人工续跑。它不是 TLS 自动重试策略：

- 停止快照、event12、请求 key/body hash 被精确绑定；旧12个事件保持原样。
- Q08 与已成功的 Q10 primer、HyDE、embedding 继续使用缓存，不产生重发费用。
- 续跑先精确补发 event12 的同一 embedding 请求，另占 event13 预留并在落盘时消耗恢复机会；其向量随后供原算法从缓存读取。官方 Local 协程到达次序可能变化，因此未消耗机会前拒绝其他新预留。该请求累计尝试上限仍为3次。
- TLS 证书、hostname 校验没有变化；若第二次仍为 TLS 错误，再次全局停止，不再自动启用人工机会。
- 模型、输出上限、查询、路由、提示词、图、评分和总预算全部不变。

旧审查门禁保留于 [首次门禁](live-readiness-before-tls-review.json)，对应 Git 提交 `2a49f33`；最新门禁另绑定一次恢复代码与独立审查。新增固定 SSL 错误类别诊断只为解释未来故障，不输出任意异常文本、凭据或证书校验绕过。
