# 统一路由运行器：离线验证与执行记录

**当前状态：92个单元已全部执行，86份有最终回答、6份失败；新增真实生成派发148次、embedding44次。** [最终账本](../results/execution.json)与[结果及复算入口](../results/README.md)记录本轮成绩。以下启动故障和离线审查是实际发生的历史过程。

[首次拦截](execution-blocked.json)与[一次重试拦截](execution-retry-blocked.json)发生在用户明确补充付费执行授权之前。用户于2026-10-14 04:24:49 UTC明确授权两个服务、公开代码材料发送与既有限额后，启动获准；随后发生的是另一件[软件故障](supervisor-incident.json)。

故障发生在旧调度器的参数断言，尚未创建worker进程。第1次生成预留仍计入累计1350次、输入1988129 token；不回退账本。修复让读取图索引只构造向量库配置，避免旧实验的全局配置副作用。[回归测试](offline_supervisor.py)在真实Data初始化后进入真实Transport.dispatch和supervisor，只有子进程为无网络的合成程序。[恢复代码](recovery.py)保留故障前快照，精确绑定该请求，下一次使用新预留；同请求合计仍最多三次，因此只剩两次实际派发机会。1883次总上限不变。

原[方案冻结清单](../freeze.json)保持原样，记录当时尚待扩额的准备状态。用户于2026-10-14 03:57:08 UTC回复“允许”，批准累计生成记录上限1600→1883；[授权记录](authorization.json)仅变更这一项，不重置1349条既有预留。

新运行器把生成、embedding、缓存和有限重试统一计账，读取既有图和向量。所有真实请求在派发前持久化预留记录，并受同一串行锁约束。没有新建图、额外探针或付费判分。断点恢复从逐次事件重建计数并核对原请求／已完成回复哈希；完整成功回复优先恢复，未确认的派发结果停止复核。

`bounded.py`负责硬预算、持久化和失败范围；`official.py`实现官方调用接口、严格格式检查与每题确定随机性；`runner.py`使用官方检索器执行冻结路由与三个基线；`transport.py`仅复用已用过的一次性HTTP worker。真实启动要求用户授权、独立审查通过和实现／输入哈希均匹配。

离线测试使用网络审计钩子，拒绝网络连接和凭据文件读取。所有假请求只写临时目录：

```sh
python3 -m unittest discover -s research/pilot/strategy-routing/runtime/tests -v
PYTHONHASHSEED=20261012 .cache/graphrag-venv/bin/python research/pilot/strategy-routing/runtime/offline_integration.py
```

[离线验证记录](offline-verification.json)保留实际测试输出与被测文件哈希。

集成检查使用真实的Microsoft GraphRAG v3.3.0查询引擎和旧图，但生成内容及新增动态查询向量是合成数据；**它验证软件接口，不提供任何新效果分数**。它覆盖DRIFT的7次生成／5次动态embedding、Global的4次map＋reduce、原80份12k上下文复用，以及新增问题的BM25／Basic／hybrid检索接口。HTTP worker也用假opener检查实际载荷，未连接服务。

实现上的明确适配：

- 每个生成调用附加同一“只根据提供的快照证据陈述事实”限制，保留完整可见请求与回复。中间答案和HyDE不是源码证据。
- Primer使用官方`PrimerResponse`字段，而不是旧社区报告schema；Local和Global map保留JSON请求。重复字段、缺字段等不会被默默接受，也不会重新付费补语义。
- 官方请求的默认`n=1`、`top_p=1`和温度参数经过校验；服务传输保持既有参数形式，不传temperature，统一请求输出2048。不能据此保证远端确定性或实际输出上限。
- 官方Global v3.3.0在`json_mode=True`时会重复传`response_format_json_object`。使用`json_mode=False`避免重复参数；map实际调用本身仍明确请求JSON。这一点由假传输集成覆盖。
- DRIFT的Local上下文也采用基线已有的共同CSV渲染器，增加真实文件／行位置；只删除尾部整行以守住4000-token预算。模型实际获得这份材料，而非仅在评分元数据补位置。
- 每题全新QueryState；HyDE模板和动作随机性按冻结规则确定。重复回放保留执行片段，证据按内容去重，单列读取次数；不把最后一段回放时间冒充全部耗时。
- 已验证的完整回复先落盘，再做内容格式检查；账户、权限、安全、全局额度和完整性错误停止整轮，题内格式或输入额度失败保留在题目分母。

新[输入哈希清单](input-manifest.json)只公开哈希元数据，绑定复用上下文、出处、缓存、图表、向量库及已安装官方查询源码；不分发缓存、模型或第三方仓库。[独立审查](independent-review.json)已通过，且[启动门禁](live-readiness.json)绑定所审查实现；真实运行仍逐次检查这些哈希。没有任何离线通过记录可以代替真实回答实验结果。

后续调度器故障的独立复核另存于[修复审查](supervisor-fix-review.json)，不会覆盖原始审查。恢复验证包括真实账本临时副本、已用预留保留、精确请求绑定和剩余两次派发限制；修复前没有成功模型结果可供调参。
