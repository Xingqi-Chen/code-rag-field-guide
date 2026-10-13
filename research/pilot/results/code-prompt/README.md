# 代码提示词实验：真实中断与恢复记录

**当前状态：第623次HTTP 503暂停，等待单独有限恢复许可。** 16:53 UTC收到JSON错误，分类`model_related`，2.280秒；未保存完整错误正文，也没有模型回复或usage，因此不猜测具体故障。615份成功生成缓存和134个导入向量核验通过。此前只批准超时／HTTP 520，控制器没有重发503。[诊断](http503-diagnosis.json)、[累计623条记录](execution-interrupted-09.json)及[待批准恢复入口](../../resume_code_prompt_http503.py)、[独立复核](http503-recovery-review.json)和[实际离线检查](verification-09.json)可核对。新入口只允许同一逻辑请求的503与超时／520共享最多两次额外尝试；120秒、累计预算和无总截止状态不变，尚未执行。

第554次因执行通道丢失而未写回账本，但HTTP 200完整回复已经落盘。恢复时离线验证547份成功回复和134个向量，554不重发；之后成功推进555–622。[恢复证据](host-recovery-554.json)记录原账本状态与未知耗时。准确的进程停止时刻未捕获，累计workflow时间含未知停机间隔，不是精确有效运行时间。

更早的HTTP 520已经获准恢复：273与272请求哈希一致，2.906秒成功，265份缓存复用。[授权](http520-authorization.json)、[配置生效](http520-retry-amendment.json)及[273成功关联](http520-recovery-progress.json)单独保存。以下保留历史诊断与阶段快照。

[HTTP 520诊断](http520-diagnosis.json)、[本次中断账本](execution-interrupted-07.json)及[恢复入口独立复核](http520-recovery-review.json)保留证据。272条预算记录中，195是未发送的行政占位，实际服务尝试271次；未知模型用量为75／96／107／108／109／272六条。文件编号跟随恢复次数，06是取消总截止前的行政停点，单独保存在[切换记录](deadline-removal-progress.json)。

总截止已于15:44 UTC按用户指令取消，单次120秒及累计预算不变。以下表格保留更早第109次停止时的历史快照。

| 项目 | 当前事实 |
| --- | --- |
| 开始 | 2026-10-13 13:12:59 UTC |
| 第一次中断 | 13:37:08 UTC；第75次60.149秒超时，74次成功 |
| 明确授权与恢复 | 13:55:34 UTC获准；13:56:18 UTC重发为第76次，34.485秒后成功；复用74份缓存 |
| 第二次中断 | 第96次60.158秒超时，于14:06:08 UTC停止；恢复阶段共20次成功，含第76次 |
| 第二次明确授权与恢复 | 14:25:48 UTC获准仅重发96一次；第97次于14:26:31 UTC发出，22.563秒后成功；复用94份缓存 |
| 第三次中断 | 第107次60.112秒超时，于14:31:29 UTC停止；本次恢复共10次成功，含第97次 |
| 新授权下的两次重试 | 5秒退避后108超时60.231秒；15秒退避后109超时60.273秒；没有第110次 |
| 生成尝试 | 109次：104次成功、5次未知；成功部分为52次初抽＋52次补抽，覆盖52／114块 |
| 已知provider输入／输出 | 430,063／220,508 token；不含未知75、96、107、108、109 |
| 实际workflow／已结束等待 | 合计2458.104秒（约40分58秒）／3618.959秒（约60分19秒）；当前等待尚未结束，另记 |
| 成功缓存复用 | 四次恢复分别74、94、104、104份，累计376次；并非376份不同回复 |
| 新embedding | 0次；仍处于逐块抽取 |
| 累计embedding预留 | 此前206,333 token，估算$0.02682329；不是发票 |
| 新图／检索 | 未完成；没有80份新Local上下文或新分数 |
| 当前失败源码块 | `src/requests/sessions.py:L1-L166` 初抽 |

[冻结计划与方法](../../code-prompt/README.md)解释本轮改动、保持不变的条件、模型与预算边界。开始前冻结提交为 `7e0c04fdd577ed346e12e4c5170e0106f224d09e`。这是已知旧结果之后的探索性验证，不是盲测。

## 可检查材料

- [取消总截止的用户指令记录](deadline-removal-request.json)、[实际配置切换](deadline-removal-applied.json)及[独立复核](deadline-removal-review.json)：仅移除总时限，保留累计预算和单次时限。
- [120秒配置切换](timeout-amendment-120.json)、[启动前独立复核](timeout-amendment-review.json)和[第110次成功证据](recovery-progress-120.json)：保留此前五次未知和全量缓存；没有重置累计预算或截止。

- [第一次中断账本](execution-interrupted.json)与[诊断](timeout-diagnosis.json)：保留原75条快照，未覆盖。
- [用户单次授权](retry-authorization.json)、[75→76恢复关联](recovery-progress.json)、[首次恢复复核](recovery-review.json)。
- [第二次中断账本](execution-interrupted-02.json)与[94份缓存及新未知请求诊断](timeout-diagnosis-02.json)：包含96条累计事件及两次未知用量；所有预算继续累计。
- [第96次恢复入口](../../recover_code_prompt_timeout96.py)及[执行前独立复核](recovery-review-02.json)：随后收到[第二次单次授权](retry-authorization-02.json)，[96→97恢复关联](recovery-progress-02.json)保留实际成功和累计缓存命中。
- [第三次中断账本](execution-interrupted-03.json)与[104份缓存及新未知请求诊断](timeout-diagnosis-03.json)：包含107条累计事件，保留三次未知和两条已使用授权。
- [第107次最初拟恢复入口](../../recover_code_prompt_timeout107.py)及[独立复核](recovery-review-03.json)：此文件保留新授权到达前的只读复核；后续实际恢复改由下述有界控制器执行。
- [本次离线验证日志](verification-03.json)：实际命令、退出码和输出；核对中断账本、原479份结果、公开文件及链接／隐私模式。
- [本轮后续超时授权](timeout-retry-authorization.json)与[恢复控制器](../../resume_code_prompt_bounded.py)：每个相同请求最多两次额外重试，5／15秒退避；鉴权、权限、预算及非超时错误不重试。
- [有限重试启动前独立复核](bounded-retry-review.json)、[第108次快照](execution-interrupted-04.json)和[第109次累计快照](execution-interrupted-05.json)：保留107→108→109精确请求关联、退避、实际时刻及未知用量。
- [重试用尽后独立终审](retry-exhaustion-review.json)与[实际离线检查日志](verification-05.json)：核对五份快照、用量、计时、24项边界测试及公开文件检查。
- [最初超时只读诊断](timeout-analysis.json)与[重试用尽后的诊断](timeout-exhaustion-diagnosis.json)：均为本机60秒硬定时器触发；没有保存到provider错误响应或部分流，无法判断具体卡在连接、等待首字节或接收响应阶段。这些历史诊断写成时，120秒尚是建议；现已按上文切换。
- [运行前检查](preflight.json)、[配置](effective-config.json)、[依赖版本](environment.json)、[启动边界复核](preflight-review.json)。
- [离线后处理复核](postprocessing-review.json)：80格／400行fixture、缓存验证与空图边界检查；是代码验证，**不是新实验分数**。
- [旧图固定抽样](quality-sample-default.json)及[独立AI审阅](quality-review-default.json)：20个实体和20条关系，17／18条主要陈述受来源支持，另3／2条部分支持。精确代码符号另计，不能用事实支持率代替检索效果或外推全图精度。新图样本尚未产生。

第107、108、109次均没有完整响应，远端完成与费用仍未知。120秒配置于15:10:19 UTC生效，第110次是原107的一次明确特别机会；其27.091秒成功低于原60秒上限，不能证明修改时限使它成功。其他新逻辑请求仍最多两次额外超时重试，5／15秒退避；累计预算不变；原2026-10-13 **16:12:59 UTC** 总截止随后按用户15:30 UTC指令取消。最终比较须披露混合时限及重试策略，不能说仅提示词／实体类型发生变化。

目前**既不能支持，也不能否定“代码专用提示词可改善效果”**，更不能证明它是此前表现差的主要原因。旧默认版结论仍只适用于旧配置。

离线复核：`python3 research/pilot/verify_code_prompt.py`。它核对冻结文件、五个中断快照、四条已获准恢复关联、重试上限、累计用量和40条旧图抽样，不调用模型或声称新检索结果。

## 抽取已完成的四个固定案例

[原文与8份完整新响应](preindex-fixed-witnesses.json)、[独立审阅的14条依据](preindex-witness-review.json)及[官方解析器交叉复核](preindex-official-parser-check.json)已完成。具体方法／链段有所补回，同时有截断边界之外的陈述；四块各漏掉补抽首条实体。这些不是最终图或Local结果，也不用于修改提示词和评分。

安装固定依赖后，可完全离线复核这四块的官方解析计数：

```bash
.cache/graphrag-venv/bin/python research/pilot/diagnose_code_prompt.py witness-parse-check --check
```
