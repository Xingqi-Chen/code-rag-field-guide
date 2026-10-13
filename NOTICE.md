# 许可与归因

本仓库原创中文说明、研究记录、教学代码、配图和检查脚本使用 [MIT License](LICENSE)。Microsoft GraphRAG 是 Microsoft 的独立开源项目，本仓库不代表 Microsoft，不是其产品或官方评测。

本轮静态研究固定于 [`microsoft/graphrag` v3.3.0](https://github.com/microsoft/graphrag/releases/tag/v3.3.0)，commit `5faaaf4f5685fa2056fa8c3bf9342cb089f2942f`。官方项目采用 [MIT 许可](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/LICENSE)。本仓库只发布研究原创产物、简短事实摘录、链接与哈希；官方完整源码仅留在本地忽略缓存，不随本仓库分发。

论文、官方文档及第三方项目名称的权利属于原作者。引用与证据边界见 [研究入口](research/README.md)，不把相近研究当作本项目运行结果。

四张配图由本地脚本原创绘制，不复制官方图片。PNG 使用已安装的中文字体渲染，不分发字体文件。没有公司代码、第三方模型权重、缓存、凭证、私人路径或私人资料入库。旧版语料与许可证的分发情况保留在[历史版本](research/legacy.md)。

真实项目使用 psf/requests v2.32.3，commit `0e322af87745eff34caffe4df68456ebc20d9068`，采用 [Apache-2.0](https://github.com/psf/requests/blob/0e322af87745eff34caffe4df68456ebc20d9068/LICENSE)，另见其 [NOTICE](https://github.com/psf/requests/blob/0e322af87745eff34caffe4df68456ebc20d9068/NOTICE)。上游完整源码／测试仓库仅在忽略缓存中下载和受控运行。实验实际检索到的原文片段及模型补丁会随逐题上下文公开，保留相对文件名、固定版本和行号；其上游部分仍适用Apache-2.0，随附[许可证](third_party/requests/LICENSE)与[NOTICE](third_party/requests/NOTICE)。模型补丁是实验输出，不是Requests官方发布或已经接受的修改。官方SWE-bench论文／数据只用于确认仓库纳入及任务元数据，没有分发其问题或答案patch。

本次公开的实体、关系、社区和社区报告是模型根据上述Requests公开语料生成的实验数据，保留源码归因与固定版本映射；不代表Requests或Microsoft认可这些描述，也不保证它们是经过验证的程序事实。其依据的第三方源码权利及许可不因模型转述而改变。
