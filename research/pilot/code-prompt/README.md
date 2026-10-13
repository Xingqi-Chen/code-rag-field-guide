# 代码专用抽取配置对照

用户要求检验“默认提示词不适合代码”是否是效果差的重要原因。新变体称为`code-prompt`：只改[抽取提示词](extract_graph.txt)和[计划](plan.json)列出的代码实体类型，保留Microsoft v3.3.0的解析、合并、聚类、描述／社区提示词与Local参数。额外保存raw_graph表仅供审计，不改变算法。

这是代码抽取配置的组合对照，不是只改提示词文字的单变量实验。提示词没有冻结题、gold、已知反例的具体符号、注入的路径或行号；只要求忠于当前块可见的定义、引用和调用依据。官方名称大写化、跨块身份、动态绑定、描述压缩及上下文分配仍保留，所以不能预先宣布主要原因已找到。

固定Requests commit、41文件／114块、20题、gold、两种模型和四档预算；新建图后生成80份Local材料，与旧BM25／hybrid／Basic／Local记录比较，不重做旧基线。原文和查询向量按精确键复用，新抽取与新图表／向量库全部隔离；不导入旧生成缓存。用户原embedding累计上限1美元从已用206333token继续记账，不重置。预计生成500–900次、约1–2小时只是按旧图估计；设置1200次／3小时停止边界，零自动重试。

状态和实际调用以[新结果目录](../results/code-prompt)为准。开始前的配置、冻结hash和环境已保存；模型调用前提交提示词／协议。复现入口使用已准备的本地依赖和用户自行配置的专用凭据；真实执行会产生远端模型费用，不能作为CI检查运行：

```bash
.cache/graphrag-venv/bin/python research/pilot/code_prompt_experiment.py prepare
.cache/graphrag-venv/bin/python research/pilot/code_prompt_experiment.py index
```

入口拒绝覆盖既有variant，也不提供自动恢复或重放命令。`check-frozen`仅检查原输入／协议／基线hash，不发请求。Global先不新增调用，待Local及新报告形成后说明是否有必要复验原六题；不扩题、不做新的功能生成。
