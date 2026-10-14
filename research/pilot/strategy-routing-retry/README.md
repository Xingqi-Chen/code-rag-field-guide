# DRIFT 失败调查与隔离重试

原实验 **13 个 DRIFT 单元中 7 个成功、6 个失败**。这次只针对失败的 Q08、Q10、Q11、Q14、Q16、Q18，原始结果与分数保留。问题、路由、提示词、GraphRAG v3.3.0、图数据、种子、预算和评分规则不变。

## 已确认的故障与证据边界

旧解码器拒绝零条、多条或空白助手文本，错误统一为 `responses_empty_or_multiple_messages`。这不符合 Responses 的多消息文本聚合语义。新解码器按官方 OpenAI SDK 2.54.0 的 `output_text` 顺序拼接；不挑选“最像 JSON”的段落、不改 JSON、不忽略冲突或拒绝信息。

六份旧失败缓存只留下一个错误类别，没有原始 SSE，不能证明六次实际都属于多消息，也不能离线恢复。它们发生在消息标准化阶段，早于 `PrimerResponse` 结构校验。详见 [原始诊断](diagnosis.json)、[解码器说明](DECODER.md)。

## 重试协议（看新结果前冻结）

- 只进入这六个已失败的 DRIFT 单元；七个成功 DRIFT、其他 GraphRAG 路由及全部基线均不重跑。
- 精确回放各题已成功的 HyDE 和 embedding；原失败 primer 的重建请求必须与旧请求逐字节等价。其余步骤继续同一官方算法，最多四个 Local 和一个 reduce。
- 继承累计 1498 次生成预留、3,095,030 个公共分词器输入 token、666,553 个 embedding token、147 次 embedding 尝试。旧六题已消耗的 20,219 个输入 token 也保留在各自 64k 上限中。
- 旧 primer 已各尝试一次，最多再允许两次物理尝试；只有超时、429、5xx 等原协议瞬态错误可自动重试。完整但无效回复不重发，不改提示词追求成功。
- 保守最多新增 102 次生成预留，累计 1600/1883；embedding 最多新增72次，累计219次，按冻结单价上界 $0.16153189。每题64k或其他限制先到即停。
- 新 run 固定为 `.cache/pilot/strategy-routing-retry-20261014`，排他锁防并发；旧 run 只读，继承清单绑定旧账本和请求/回复哈希。
- 新 worker 在解码前保存完整、大小受限的私有原始回复，权限0600；仅公开规范化可见文本、固定类别诊断及用量，不公开凭据、响应头、辅助推理或模型向量。
- 内容评分沿用冻结的87条标准，不因重试修改旧评分。新六题答案单独匿名评分，原成功单元与三个基线分数直接复用；修复后整体分数与原始结果并列，不能覆盖原表。

## 执行

真实调用必须通过绑定源码与输入的独立审查门禁，使用本地原有凭据；脚本不安装依赖、不创建权限。需要原实验缓存、固定语料和本地 GraphRAG 环境。

```sh
PYTHONHASHSEED=20261012 PYTHONDONTWRITEBYTECODE=1 .cache/graphrag-venv/bin/python research/pilot/strategy-routing-retry/test_responses_decoder.py
caffeinate -i env PYTHONHASHSEED=20261012 PYTHONDONTWRITEBYTECODE=1 .cache/graphrag-venv/bin/python research/pilot/strategy-routing-retry/runner.py execute
```

此次是已知题目上的实现修复与条件重试，不是新的独立盲测。重复调用还引入模型随机性；没有原始失败回复，不能把修复后变化全部归因于多消息兼容性修复。
