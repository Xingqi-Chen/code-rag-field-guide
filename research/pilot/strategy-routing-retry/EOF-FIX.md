# 确证 EOF 的分类修复

第二次运行再次按原停止规则退出。event13 精确补发了此前失败的向量请求并成功；event14 的另一个向量请求也成功。event15 在发送 Q10 的一个 Local 生成请求时出现：

```json
{"class":"SSLEOFError","ssl_reason":"UNEXPECTED_EOF_WHILE_READING","verify_code":null}
```

这是这次 worker 实际保存的固定诊断，不是对 event12 或原六次 primer 故障的推测。完整绑定记录见 [eof-stop.json](eof-stop.json)。

Python 官方文档把 `SSLEOFError` 定义为 TLS 连接突然终止，并建议不要复用底层连接；证书验证失败使用独立的 `SSLCertVerificationError`。这不证明服务器未收到请求，也不证明其不计费。[Python 3.12 ssl 官方文档](https://docs.python.org/3.12/library/ssl.html#ssl.SSLEOFError)，访问2026-10-14。

原分类器先判断所有 `SSLError`，一律归为 `transport_security_error`，因而把这个提前断连也当作安全故障。修复只在本轮新 worker 中按真实 `SSLEOFError` 异常类型识别，不靠错误字符串猜测；既覆盖 `URLError.reason` 包装，也覆盖读回复时直接抛出。它进入原有 `transient_connection_error` 路径，最多三次累计尝试，使用原5／15秒退避。每次都创建新 worker、新连接、原 certifi CA 和 hostname 校验。普通 SSL、证书、权限、鉴权等错误仍立即停止，旧实验分类代码不变。

event15 的原错误标签、未知用量和预留保持原样。单独的修复恢复记录绑定停止快照和具体异常，只允许先按原请求填充 event16 缓存，再恢复原 Q10 流程。event15 已占一次，因此最多再两次；没有完整回复时不把费用当零。Q08和 Q10已成功的请求继续从缓存读取。

这是新增的可核实实现修复；不把它倒推成原六次 primer 错误的原因，也不把原 event12 未知 SSL 原因追认为 EOF。最初一次人工 TLS 续跑的机会已消费，未再次启用；此次依据的是新保存的明确异常类型及其独立复核。
