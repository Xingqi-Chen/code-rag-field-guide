# 小批接口探测：初抽和embedding通过，补抽500后停止

**更新后的凭据已通过一次生成请求，两批OpenAI embedding也通过了检查；随后第一块的补抽请求返回HTTP 500，按约定立即停止。** 没有自动重试、替代模型或扩大到完整评测。原来的401失败保留且计入总额度。

## 两次人工授权，沿用一份总额度

| 阶段 | 实际请求与结果 | 探测进程时长 |
| --- | --- | ---: |
| 首次批准批次01 | 1次生成接口请求→401，零embedding，停止 | 1.175秒 |
| 用户更新key后明确授权的续批02 | 初抽200→源码embedding 200→dev查询embedding 200→补抽500，停止 | 16.376秒 |
| 累计 | **生成3/17次，embedding 2/3批**；未重置次数或token | **17.551秒／20分钟** |

两次实际执行分别发生于2026-10-12的15:08和15:27 UTC，执行地点均为Mac mini。前面的离线工程准备另计；`started_utc`是各自本地预检后的账本建立时刻，进程总时长包含更早的初始化。续批的四次请求监督等待分别为3.456、5.092、1.847、5.698秒，包含子进程启动和收尾，不能当作纯服务端延迟。

[首次原始脱敏记录](probe-result.json)没有回写；[续批逐请求脱敏记录](key-update-result.json)记录继承额度、输入ID/hash、状态、usage和时间。续批前确认旧监督进程已退出、原worker已结束，没有并发重复请求。新的固定目录只允许这一次人工触发，失败后仍禁止自动重开。

## 已经验证到哪一步

| 检查 | 实际结果 | 不能据此声称什么 |
| --- | --- | --- |
| one.fullstar初抽 | HTTP200，响应model为 `gpt-5.6-luna`，按当前格式检查通过；只有完成标记，0实体／0关系 | 不代表代码抽取质量好，也不能证明代理内部模型映射或限额执行 |
| 8块源码embedding | HTTP200，8个3072维向量，数值有限、index完整；usage为4,247输入token | 尚未测检索召回或下游回答 |
| 4条dev查询embedding | HTTP200，4个3072维向量，数值有限、index完整；usage为80输入token | 未向服务发送test问题／gold，也未做题集评分 |
| 第一块补抽 | **HTTP500**；脱敏分类为model相关，立即停止 | 分类只反映错误内容涉及model，不能确定是模型本身、代理配置还是临时服务故障 |
| 报告JSON与图产物embedding | 未到达 | 不得称微软完整流程兼容 |

生成请求带2048输出token上限。唯一成功回复报告prompt／completion／total为 **3,490／99／3,589**，可见文字按共同词表计6token。两种计数定义不同，不能把可见文本计数当账单；一次短输出也不能证明服务必然执行了最大输出限制。one.fullstar费用按用户要求不估算。

OpenAI两批返回的usage合计 **4,327 token**，与本地cl100k计数一致；按[官方普通输入价](https://developers.openai.com/api/docs/models/text-embedding-3-large) $0.13／百万，输入费用计算为 **$0.00056251税前**，低于批准的$0.01。未独立核对账单；没有其他OpenAI请求。价格访问日2026-10-12。

累计预留生成输入为 **6,391个o200k共同计数token／100,000**，embedding为 **4,327／20,000**；失败不退回额度。剩余14次生成、1批embedding及未用预算没有被自动继续使用。

## 如何保证没有重置或偷偷增加调用

续批继承首次失败的1次生成、2,112输入token及1.175秒。[执行前记录](key-update-plan.json)预先将新增生成设计压到16次：8次初抽＋7次补抽＋1次报告格式检查，省去固定第8块的补抽；并将源码与dev两批embedding前置，优先验证核心接口。这是用户要求在剩余额度内安排，不是看结果后挑题。实际遇到新500错误便停止，未走完该设计。

用户取消资源监控后，当前脚本不含RSS、CPU或进程树采样。保留发送前持久预留、一次性发送槽、固定endpoint、禁止重定向、并发1、零客户端自动重试、失败即停、60／30秒请求与20分钟累计进程超时。服务公开schema列出的 `num_retries=0` 和空fallback亦随生成请求发送；远端实现仍不能从本次结果完全验证。

[所选服务公开OpenAPI](https://one.fullstar.tech/openapi.json)确认了POST路径 `/v1/chat/completions`，[路由证据](endpoint-evidence.json)记录文档hash和自报版本。探测采用直接HTTP及固定微软prompt，**未安装／执行Microsoft GraphRAG或LiteLLM包**；因此不替代完整客户端集成检查。

密钥位于用户手动设置的仓库外文件。此前经授权核实归属／非符号链接并收紧至700／600，更新后权限仍符合；只由请求子进程在内存加载对应变量。没有回显、复制、提交密钥或保存请求头。公开的是统计和脱敏记录，完整请求／响应及向量缓存不发布。没有使用本机或云浏览器。

## 可复核材料与剩余边界

首次执行代码固定于提交 `ec3c3a9d6243ebfdf1608bdae966aa79e8c40248`，见[hash记录](runtime-pin.json)。取消监控后的人工续批代码固定于 `629cb6783a6f72f16819e4b3ebc428cc5ab6b075`，见[续批执行前hash](key-update-plan.json)。首次发送前9项离线检查通过；续批新增继承额度测试后9项检查通过，见[续批日志](key-update-checks.log)。独立审阅者核查了两次发送前的额度与凭据边界；这些检查不是GraphRAG效果实验。

8块完整抽取、报告schema、图产物向量、微软索引、检索评分和feature改码均未完成。本轮证明了一次初抽请求和两批官方embedding可以返回通过当前校验的结果；补抽失败使完整兼容性仍未验证。原题集、gold和评估协议未变，没有依据成绩调题。

若用户希望排查500后再次尝试，必须明确授权，并继续累计已有消耗；本轮不自动修复或重启。只复核当前公开证据可运行：

```bash
python3 -m unittest discover -s tests
python3 research/pilot/verify.py
python3 research/pilot/verify_selection.py
python3 research/pilot/verify_probe_result.py
python3 scripts/validate.py
```

CI只运行离线检查，不加载凭据、不发模型请求。

## 离线传输修复（2026-10-12）

当前[运行器](probe_runtime.py)改为同一服务的 `/v1/responses`，使用 `input`、`max_output_tokens=2048`、`stream=true`、`store=false`。原Microsoft抽取／补抽prompt、题集和解析规则未改；报告schema只改为Responses的 `text.format` 表达。接收端兼容JSON和SSE，在最终 `completed.output` 为空时，从已完成且编号连续的 `output_item.done` 恢复；只收到delta、真正空输出、不完整／失败状态、断流、重复／冲突数据均不算成功。辅助reasoning内容不进入保存结果。usage映射后仍检查模型、总量一致性与2048输出限制，但接收后的检查不能约束上游已发生的生成。

8项新增合成样例测试通过，连同原测试共25项；离线预检通过，未读取凭据、未发请求。[样例与检查代码](../../tests/test_responses_transport.py)。**所有真实调用CLI入口保持禁用；这证明本地解析行为，尚未证明远端兼容或修复了本次500。** 原两份实测记录及执行提交保留不变。

公开LiteLLM版本核查：v1.94.0（`38f2e023f1179d06a199f3d5f02702c89c1a8a58`）及2026-10-12的main提交 `7efce7f8e05e58fb86e006a6427ab39b6db467fb` 均在chatgpt适配器中强制上游stream，并以允许字段过滤请求；其中没有 `max_output_tokens` 或 `text`。这是公开源码事实，**不是对服务当前部署版本的确认**。直接Responses也不能保证上游执行输出上限或schema；本地仍严格验证返回结果。[v1.94.0源码](https://github.com/BerriAI/litellm/blob/38f2e023f1179d06a199f3d5f02702c89c1a8a58/litellm/llms/chatgpt/responses/transformation.py#L55)、[当前固定源码](https://github.com/BerriAI/litellm/blob/7efce7f8e05e58fb86e006a6427ab39b6db467fb/litellm/llms/chatgpt/responses/transformation.py#L64)，访问日2026-10-12。

原两批缓存向量已离线复验，可以复用8个源码向量和4个dev查询向量，无需重发。当前累计仍为生成3/17、embedding 2/3；剩余14次生成、1批embedding、15,673个embedding输入token及9个item。最后一批仅足以在原限制内用于小样本图产物，不代表可完成114块全量索引。

下一次最小续试建议仅重发第一块的补抽：同服务、同模型、相同三条消息，经Responses发送1次生成、0次embedding，仍请求2048上限，60秒超时，失败即停且不重试；发送后累计为4/17和2/3。需先由服务端确认上限能执行，或由用户明确接受“请求上限不保证上游实际上限”的这一单次尝试；本地超时也不能保证远端停止计算或计费。该建议尚未获得执行授权，没有提高或重置原总额度。
