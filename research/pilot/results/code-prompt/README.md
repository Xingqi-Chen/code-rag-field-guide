# 代码提示词实验：真实中断与恢复记录

**当前状态：第1,091次遇新的JSON格式错误，已停止。** 2026-10-14 01:22:28 UTC，第116份社区报告回复含4个对象末尾多余逗号，未通过原版JSON解析。前115份可用，其中1027使用了一次已获准格式例外；1091不在该许可内，没有修复或重发。新索引、embedding与Local评分未完成。

[第12份停止快照](execution-interrupted-12.json)、[1091完整原文与精确候选](schema-1091-diagnosis.json)及[独立复核](schema-1091-review.json)已保存。仅删除4个字符串外逗号后，原schema通过、全部字符串与5条findings保留；候选未用于正式流程。1091 HTTP200、finish stop，已知provider输入4,252／输出1,029 token，未把格式失败记为未知用量。可离线运行`python3 research/pilot/diagnose_code_prompt_schema.py --event 1091 --check`。

此前用户于2026-10-14 01:03:05 UTC明确批准仅1027删除4个对象末尾逗号，按原schema验证后继续，不重发、不做其他JSON或语义修复。01:10:51 UTC在读取精确缓存时成功应用；原response／cache哈希和usage均保持不变，1028作为不同的新报告请求随后成功。1,018份原生成回复及134向量核验复用，累计缓存命中3,780。[授权](schema-1027-authorization.json)、[实际配置](schema-1027-amendment.json)、[恢复前独立复核](schema-1027-resume-review.json)及[实际继续证据](schema-1027-progress.json)保留全过程。

此前2026-10-14 00:55:31 UTC，第1,027次HTTP200完整回复因4个对象末尾多余逗号未通过原版JSON解析而停止。前51份报告格式有效，第52份当时只有传输／内容完整性验证通过；不能把52次成功HTTP调用写成52份有效报告。

[中断账本](execution-interrupted-11.json)保留1,027条生成预算记录：195和675未派发，实际服务尝试1,025次；七次原模型用量未知继续保留。图表已生成1,628实体、2,891关系、372个跨层社区。新embedding调用仍为0。

[原回复与候选修复](schema-1027-diagnosis.json)仅作离线审查：删除原字符串外、对象闭括号前的4个逗号后，原版schema通过，全部5条findings保留；原回复、缓存、账本和在线解析器未改，没有新模型调用。[独立复核](schema-1027-review.json)检查字符串内容逐字不变。此错误不属于既有临时网络重试许可；候选诊断文件保留批准前状态，随后获得上述单次例外许可，未重发成功请求。可离线运行`python3 research/pilot/diagnose_code_prompt_schema.py --check`复核公开候选。

此前00:24:02 UTC用户批准超时、连接中断、429和5xx共享每请求最多两次额外尝试，遵守Retry-After；00:31:24批准生成预算记录上限提高至1,600，其余预算不变。623→624在4.372秒成功，615份成功缓存复用；675为从未发送的额度检查点，切换时再复用666份成功回复。

[统一重试授权](transient-retry-authorization.json)、[实际切换](transient-retry-amendment.json)、[成功关联](transient-recovery-progress.json)、[独立复核](transient-retry-review.json)及[额度变更](generation-cap-amendment.json)记录此前恢复状态。[原503诊断](http503-diagnosis.json)和[暂停快照](execution-interrupted-09.json)不覆盖。之前准备的503单独恢复入口未执行，实际使用统一策略入口。下面是此前停机与恢复的历史事实。

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


## 固定四例的实际图记录审查

[独立审阅](fixed-graph-review.json)检查图表稳定快照，包含51条最终实体／关系及25条必要原始候选、源码短引和可复算语义哈希。具体方法与header语义改善进入图，同时仍有同名身份混合、类型／定义来源保留不足和部分关系来源不足；有些片段外推获得相邻来源补证，逐条区分。它没有查看新Local分数，也不估计全图精度。372社区包含全部层级，未改变官方社区配置或只选局部层级省去报告。

[离线评分准备复核](scoring-readiness-review.json)验证400行对照和15条可评分test的代码路径，修正了完成验证器及缺失耗时标签；内存fixture不等于真实80份新上下文已经完成。


大型公开图表将按页保存：主JSON列出有序分片、逐片hash与整表逻辑hash，不省略字段或记录；`index_artifacts.read_table`验证后重组原顺序。分页只涉及公开文件组织，不影响私有parquet索引、检索参数或评分。当前尚未导出完成索引，分页往返及篡改拒绝测试已通过。
