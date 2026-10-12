# 首次真实探测：认证失败，按约定停止

**2026-10-12在Mac mini执行了唯一获准的小批探测。第1个生成接口请求返回HTTP 401，整批立即停止；没有重试、替代模型或新批次。** 没有取得生成结果，也没有向OpenAI发送embedding请求。因此本次只能证明“所用认证未通过”，不能判断指定模型、输出限额、JSON格式或代码检索是否有效。

| 实际发生的事 | 记录 |
| --- | --- |
| 生成服务与请求模型 | one.fullstar.tech，`gpt-5.6-luna` |
| 已发送生成接口尝试 | **1**，上限17；第一块的初次抽取 |
| 服务返回 | **HTTP 401**；JSON错误归类为认证相关，未保留错误中的自由文本／URL |
| 模型输出／计费用量 | 未取得模型输出或usage；不把本地token计数当服务账单 |
| 预留输入 | 2,112个 `o200k_base` token，按实际序列化请求体计；失败不退回额度 |
| 请求监督等待 | **0.894秒**（包括子进程启动／收尾，不是纯服务端延迟） |
| 探测进程总时长 | **1.175秒**，包括启动后的本地预检；离线工程准备另计 |
| OpenAI请求／输入费用 | **0次／$0**；其密钥有效性、embedding维度和usage均未经过真实验证 |

[逐请求脱敏记录](probe-result.json)保留了样本ID、请求体hash、时间、状态及额度。`started_utc` 是本地预检后的账本建立时刻（15:08:45 UTC），总时长从更早的探测进程初始化计起，两者定义不同。one.fullstar费用按用户要求不估算；HTTP 401不能替代服务账单核对。

## 执行前做过的检查

用户明确授权后，只将本项目仓库外凭据目录和文件收紧至700／600；先核实归属并拒绝符号链接，没有修改其他路径。密钥仅由请求子进程在内存中加载，不放进命令行、Git、stdout/stderr或日志。文件非空与权限检查通过，**不等于远端认证有效**。

从所选服务公开首页找到 `/openapi.json`，核实了 `/v1/chat/completions` 的POST路由；文档自报LiteLLM API 1.94.0，访问日2026-10-12，原文未列发布日期。[公开文档](https://one.fullstar.tech/openapi.json)及[本次hash与路由摘录](endpoint-evidence.json)。这验证的是文档中存在该路由，不是模型映射已验证。公共文档首读曾返回403，改用普通浏览器User-Agent后读到200；该步骤无凭据、非模型调用，没有使用浏览器界面。

[运行脚本](probe_runtime.py)采用直接HTTP，静态读取固定微软prompt，不安装或执行GraphRAG／LiteLLM包。这避免在兼容性探测阶段启动完整索引，但**不能替代未来微软客户端集成检查**。脚本实现了发送前落盘预留、固定批次目录独占、一次性发送槽、固定endpoint、禁止重定向、无客户端重试、失败即停和参数校验。服务公开schema列出的 `num_retries=0`、空fallback等亦随请求发送；远端是否执行这些设置仍未验证。输出请求上限保持2048，未因未验证而静默删除。

整批20分钟报警、单请求60／30秒监督与独立子进程终止已接通。**用户随后取消资源监控：当前脚本已移除RSS采样、进程树监控及2GiB阈值**，保留次数、token、输出、费用、超时、并发1、零重试及失败即停。本次请求发生在取消之前；实际执行版本保留在Git提交 `ec3c3a9d6243ebfdf1608bdae966aa79e8c40248`，原始脱敏记录不回写，也没有再次运行。

发送前，独立审阅者核查了额度、一次性批次、凭据与停机路径，并确认未证实的 `drop_params` 已从HTTP字段移除。当时9项短离线测试通过；[真实检查日志](runtime-checks.log)、[执行代码hash](runtime-pin.json)可核对。取消资源监控后只重跑8项短离线测试，见[清理检查](runtime-cleanup-checks.log)；没有读取凭据或发送新请求。

## 这次没有完成什么

8块抽取、报告JSON、OpenAI向量化、微软完整索引、检索评分、feature改码均未完成。401发生在认证关口，无法区分令牌内容、令牌权限或服务认证配置等具体原因，也无法判断后面的 `max_completion_tokens` 或schema参数会不会被接受。

本批次已经关闭，脚本会拒绝同一目录的再次执行。后续需要用户核对one.fullstar凭据与权限，并**另行授权新的兼容批次**；失败后未再次读取或修改密钥内容，没有自行修复后重启。原题集／gold／协议未变，未根据任何方法成绩改题。

[selection.json](selection.json)及[选定YAML](ms-settings.selected.yaml)记录最初模型选择；[probe.md](probe.md)已标注真实执行结果及用户撤销资源监控的修订。没有改动原题集／gold／协议冻结文件，也没有假装调用在冻结前发生。现在的可执行边界以本页为准，完整Microsoft运行适配器仍未完成。

## 只复核，不再调用

```bash
python3 -m unittest discover -s tests
python3 research/pilot/verify.py
python3 research/pilot/verify_selection.py
python3 research/pilot/verify_probe_result.py
python3 scripts/validate.py
```

发布物只包含原创脚本、统计与脱敏结果；完整第三方源码、提示词原文、权重、凭据、请求／响应缓存均不提交。CI只运行离线检查。
