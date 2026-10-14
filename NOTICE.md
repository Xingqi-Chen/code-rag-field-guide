# 许可与归因

本仓库原创中文说明、研究记录、教学代码、配图和检查脚本使用 [MIT License](LICENSE)。Microsoft GraphRAG 是 Microsoft 的独立开源项目，本仓库不代表 Microsoft，不是其产品或官方评测。

本轮静态研究固定于 [`microsoft/graphrag` v3.3.0](https://github.com/microsoft/graphrag/releases/tag/v3.3.0)，commit `5faaaf4f5685fa2056fa8c3bf9342cb089f2942f`。官方项目采用 [MIT 许可](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/LICENSE)。本仓库发布研究原创产物、事实摘录、链接与哈希；Global实验逐次请求保留实际使用的官方map/reduce提示词，失败链见证保留8份抽取请求中的官方提示词，随附 [Microsoft GraphRAG MIT 许可及版权声明](third_party/microsoft-graphrag/LICENSE)。官方完整源码仅留在本地忽略缓存，不随本仓库分发。

论文、官方文档及第三方项目名称的权利属于原作者。引用与证据边界见 [研究入口](research/README.md)，不把相近研究当作本项目运行结果。

四张配图由本地脚本原创绘制，不复制官方图片。PNG 使用已安装的中文字体渲染，不分发字体文件。本轮研究工作文件未加入公司代码、第三方模型权重、缓存、凭证、私人路径或私人资料；正常Git作者元数据仍保留，不声称全部历史匿名。旧版语料与许可证的分发情况保留在[历史版本](research/legacy.md)。

真实项目使用 psf/requests v2.32.3，commit `0e322af87745eff34caffe4df68456ebc20d9068`，采用 [Apache-2.0](https://github.com/psf/requests/blob/0e322af87745eff34caffe4df68456ebc20d9068/LICENSE)，另见其 [NOTICE](https://github.com/psf/requests/blob/0e322af87745eff34caffe4df68456ebc20d9068/NOTICE)。上游完整源码／测试仓库仅在忽略缓存中下载和受控运行。实验实际检索到的原文片段及模型补丁已随逐题上下文公开，保留相对文件名、固定版本和行号；其上游部分仍适用Apache-2.0，随附[许可证](third_party/requests/LICENSE)与[NOTICE](third_party/requests/NOTICE)。模型补丁是实验输出，不是Requests官方发布或已经接受的修改。官方SWE-bench论文／数据只用于确认仓库纳入及任务元数据，没有分发其问题或答案patch。

本次公开的实体、关系、社区和社区报告是模型根据上述Requests公开语料生成的实验数据，保留源码归因与固定版本映射；不代表Requests或Microsoft认可这些描述，也不保证它们是经过验证的程序事实。其依据的第三方源码权利及许可不因模型转述而改变。

后续失败链诊断另公开四个Requests原文块与对应八份原样模型可见抽取回复，用于核验遗漏和错误传播；上游原文仍按上述Apache-2.0许可与NOTICE归因，不包括完整第三方仓库。更新处理微测仅发布原创假文档、调用脚本和结果，固定版微软函数仍从本地依赖加载。

代码提示词追加实验公开的80份检索上下文、固定抽取见证、质量样本短引和原报告格式审计沿用上述Requests固定版本、Apache-2.0许可与NOTICE；默认抽取对照涉及的微软官方提示词沿用随附MIT声明。新增代码抽取提示词和审计脚本为研究原创，不分发缓存、模型权重或完整上游仓库。

统一路由回答实验公开的逐次请求含微软Local／Global／DRIFT官方提示词及其明确披露的接口适配，沿用随附Microsoft MIT版权与许可；请求中的Requests源码、文档和测试片段沿用Apache-2.0及NOTICE。原始可见模型回复、逐题判断、路由和聚合脚本为研究记录；模型回复中的错误陈述不是上游事实。公开规范化回复，不分发原始网络事件流、embedding向量、模型权重或私有服务配置。

六个原失败DRIFT单元的重试公开材料遵循同一固定版本、来源映射和上述许可。私有原始事件流只用于诊断，公开其哈希及不含隐藏推理文本的结构计数；新旧可见回复的兼容性比较不改变上游源码归因。
