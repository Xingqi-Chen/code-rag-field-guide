# 本项目的密钥放在哪里

在 Mac mini **由用户手动创建**仓库外文件 `~/.config/code-rag-field-guide/credentials.env`。不要把密钥贴进聊天、已跟踪YAML或公共仓库。准备和CI检查不读取该文件；获准的HTTP探测仅由请求子进程在内存加载对应服务的变量，不显示值。首批401后用户更新key并授权续批，初抽成功、补抽500后已停止，见[真实记录](probe-result.md)。

文件使用下面两个独立变量，值由用户在本机填写：

```dotenv
CODE_RAG_FULLSTAR_API_KEY=用户的one.fullstar密钥
CODE_RAG_OPENAI_API_KEY=用户的OpenAI官方密钥
```

建议目录权限700、文件权限600。可参考[无密钥示例](credentials.env.example)，手动复制到上述位置后再填写。不要把密钥写进命令行参数或shell历史。

[选定模型模板](ms-settings.selected.yaml)仅引用 `${CODE_RAG_FULLSTAR_API_KEY}` 与 `${CODE_RAG_OPENAI_API_KEY}`。前者用于 one.fullstar.tech 的 `gpt-5.6-luna`；后者用于 OpenAI 官方 `text-embedding-3-large`，3072维。hybrid/Basic/Local共享同一embedding模型。

**保存文件不会自动开始。** 当前HTTP探测脚本采用安全文件读取，不导入微软loader；完整Microsoft运行适配器尚未接通。固定版 `graphrag_common.config.load_config` 已支持显式 `dot_env_path`；后续接入微软时应指定上述仓库外文件，并将无密钥YAML复制为独立运行目录的 `settings.yaml`。普通GraphRAG loader默认只找配置旁的 `.env`，不会自动找到 `~/.config/`。只通过两个本项目变量传入，不回退到其他项目的通用key；配置或错误输出禁止包含解析后的密钥。

仓库 `.gitignore` 已忽略 `.env`、`.env.*`、`*.env` 和 `.cache/`；示例文件允许跟踪。仓库外文件本身不属于Git工作树。非空检查不能验证密钥有效或服务可用，不能打印其值验证。

生成接口路径及模型映射尚未探测，模板保留endpoint占位符，不能宣称可直接运行。one.fullstar不再等待费用计算；仍需限制调用、token、时间和重试。[8块probe范围与OpenAI限额](probe.md)已列出，首次401后仅按用户更新key的明确授权人工续批一次，继承原消耗；补抽500后停止，见[真实记录](probe-result.md)，没有自动重试。

加载行为依据：[固定Microsoft配置加载器](https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-common/graphrag_common/config/load_config.py#L106-L182)，2026-10-12静态核对，未执行密钥加载。
