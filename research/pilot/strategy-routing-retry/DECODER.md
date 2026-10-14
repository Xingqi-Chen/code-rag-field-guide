# DRIFT 重试前的解码器调查

**已经证明旧解码器会错拒合法的多消息文本输出；尚未证明历史 6 次失败就是这个原因。** 新目录只做响应结构兼容，不改变问题、提示、路由、检索策略或旧评分。真实重试及新账本由独立执行器管理，这份检查不授权或证明已经重试。

## 失败在哪里

旧 `probe_runtime.py:254–255` 将 reasoning 类型排除后，要求恰好一条非空 assistant 消息，否则抛出 `responses_empty_or_multiple_messages`。这个错误把零条、多条和单条空白混在一起。旧 worker 在解码后才构造要保存的 HTTP 状态、回复和用量；解码抛错便只保留错误分类。历史 6 次因此没有完整失败 SSE/JSON 正文、Content-Type 或已记录的 HTTP 状态，不能反推出服务具体返回了什么。

`runtime/transport.py` 只调用这个 worker 并传回结果，没有第二套可恢复的原始回复。`code_prompt_transport.py` 捕获连接错误与 Retry-After，没有修复消息内容。`official.py` 在 `cell.generate` 返回后才运行严格 JSON 和 `PrimerResponse.model_validate`；历史报错尚未到 JSON 字段校验。

固定 GraphRAG v3.3.0 的 [primer.py](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/drift_search/primer.py) 要求 `intermediate_answer: str`、`score: int`、`follow_up_queries: list[str]`，并从 `formatted_response.model_dump()` 取结构化结果。2000 字符和至少 5 个追问写在字段描述里，不能误称为该 Pydantic 模型的硬长度验证。现有实验另有严格字段、非空追问及预算规则，本次继续保留。

## 新解码器怎样修复

本机 OpenAI Python **2.54.0** 的 `Response.output_text` 将所有 message 里的 `output_text` 按输出顺序直接连接；[同版本官方源码](https://github.com/openai/openai-python/blob/v2.54.0/src/openai/types/responses/response.py) 明确允许 output 长度由回复决定。来源访问日为 2026-10-14；本机源码及版本元数据哈希见 [decoder-review.json](decoder-review.json)。这是一条响应格式依据，不是六次故障的历史证据。

[responses_decoder.py](responses_decoder.py) 采用这个聚合规则，保留 completed 终态检查、SSE done-item 与终态一致性检查、连续索引恢复、拒绝重复/冲突事件。还拒绝重复终态 output ID，并将畸形事件类型转为固定错误码。reasoning 内容不进入返回值或诊断；refusal、工具输出和未知输出类型仍失败。用量、模型、可见和供应商输出限额继续由调用者验证。

- 两条文本刚好是一个 JSON 的两段：顺序连接后交给原严格 schema 校验。
- 一段说明加一份 JSON，或两份完整 JSON：忠实连接，随后严格 JSON 校验失败。**不选最像 JSON 的消息，不剪代码围栏，不补字段。**
- 真正空白或只有 reasoning：仍失败，单独报 `responses_empty_visible_output`。
- 仅有 delta、未完成、重复、冲突、refusal：不当作成功，也不靠部分文本补答案。

接口为 `decode_generation(raw, content_type, diagnostics=metadata)`。失败抛 `DecodeError`，其文本只有固定错误码，`.diagnostics` 是不含回复文本的状态、计数和数值用量。调用 worker 需显式捕获该类型，再决定持久化事件，不能让它跌入没有诊断的泛异常处理。诊断用量只在整数非负且总量相等时填入；没有用量就是未知，不是零。

## 完整 raw 与公开材料的边界

新 worker 应在任何 decode 前保存收到的 **原始 body 字节** 到新的隔离缓存：目录 0700、文件 0600、排他创建、拒绝符号链接、落盘后记录 SHA256。保留 HTTP 状态、白名单 Content-Type、收到的字节数、读取上限和是否完整。不要保存请求 Authorization、完整响应 headers、cookie 或账户相关头。沿用有界读取；超限/中断只能称保存了“部分 raw”，不能宣称完整。

完整 raw 可能含有 reasoning、服务内部信息或凭据回显，因此只能作为私有诊断材料，禁止直接输出终端、交给报告或自动进入 Git。公開材料应另用白名单导出，仅包含可见答案、结构计数、有效用量、固定错误类别和哈希；排除 reasoning、任意服务错误文本及原始头。对当前凭据的原文与 JSON 转义形式作回显检查；一旦发现回显，停止普通导出并隔离，绝不把它打印成诊断。脱敏后的副本要单独命名、单独哈希，不能把它称为字节原样的完整响应。仅做字符串替换不构成“任意敏感信息一定清除”的保证。

这部分是 worker 集成要求；本模块没有文件、网络、凭据读写，也没有 raw 保存实现。即使新试验修复成功，也不能恢复已经丢失的旧 SSE 或据此改写旧结果。

## 离线复核

```bash
.cache/graphrag-venv/bin/python -B research/pilot/strategy-routing-retry/test_responses_decoder.py
```

28 项通过，包括合成 JSON/SSE 多消息、旧版拒绝与新版聚合的差异、实际安装 SDK 属性的等价检查、错误/空白/重复/冲突/不完整负例，以及原严格 JSON/固定 PrimerResponse 的校验。7 条历史成功 primer 的**已归一化可见文本**仍通过原 schema；这不是原始 SSE 重放。全部测试无 API、无凭据、无实验重跑，旧文件 SHA 保持不变。
