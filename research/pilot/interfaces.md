# Microsoft pilot：配置与只取上下文的接口契约

准备记录，访问日 **2026-10-12**，固定 Microsoft GraphRAG **v3.3.0 / `5faaaf4f5685fa2056fa8c3bf9342cb089f2942f`**。未安装、导入或执行微软代码；未调用本地或远程模型。模板是 [ms-settings.template.yaml](ms-settings.template.yaml)，模型、提供方、endpoint、鉴权与向量维度均待选择。它不是已验证可运行的配置。

## 配置与工作流

- 官方包要求 Python **`>=3.11,<3.14`**。模板使用 3.x 的 `completion_models`、`embedding_models`，不是旧版单一 `llm` 配置。[包配置] [初始化模板]
- `type: litellm` 是适配器类型；`model_provider` 和 `model` 仍是占位符。`api_base`、`api_key`、`call_args` 均为真实字段。模板展示 `api_key` 鉴权语法；若最终选择 Azure managed identity，应改 `auth_method` 并去掉 `api_key`。无鉴权本地兼容服务的虚拟 key 也只能在明确选择后配置。不要把任何真实凭据写回模板。[模型配置]
- `vector_store.vector_size` 是整数，默认索引 schema 从它取得维度。当前字符串占位符故意阻止正式类型验证通过；不能假定所有 embedding 都是默认的 3072 维。[向量配置] [总配置]
- `embed_text`、Basic、Local 全部引用同一个 embedding 配置 ID。后续所有对照方法必须共用同一具体模型/版本、维度、输入规范与归一化约定；相同配置 ID 本身不能证明外部向量与该模型一致。
- 显式 workflows 对应上游 Standard 顺序，**覆盖** `method` 选择。保留这个列表时不能把运行标作 Fast。`extract_covariates` 在 claims 关闭时不代表启用了 claims；默认抽取类型和内置抽取/摘要/报告 prompts 保持不变。`prompt: null` 走内置 prompt，并非禁用 LLM。[工作流] [抽取配置] [报告配置]
- 并发 1、显式 retry 设置是试点参数，必须随运行记录；不能据 `max_retries` 推算真实物理请求数。相对路径以独立 run root 为基准，输出/缓存需按源码快照及配置隔离。[模型配置] [重试配置]

## 共享输入适配与来源

每个 JSONL 对象含 `id,title,text`；来源 metadata 放在独立 sidecar。输入 producer 已按完整源码行切块：每块不超过 1200 个 `o200k_base` token，块间仅保留不超过 100 token 的整行重叠；`title=relative_path:Lstart-Lend`，`text` 是原始源码行，来源 sidecar 保存 commit、相对路径、行区间和输入 ID。这是**共享输入适配**，不是未修改的 upstream 默认文件切分。

微软侧仍使用官方 token chunker，但设 `size: 1200`、`overlap: 0`、`prepend_metadata: null`。后者字段类型为可空列表，不能写布尔 `false`。不把路径、commit、行号附进正文，不让某种方法单独多看提示信息。结构化 reader 明确映射 id/title/text，并把整行对象保存在 `raw_data`；metadata 没有专用配置列，也不会自动传播为查询 Sources 列。[输入配置] [结构化 reader] [块配置]

后续 runner 的输入验收必须先于效果评分：

1. 自行严格检查 JSONL 行数、对象格式、ID 唯一性与来源范围；官方 JSONL reader 对坏行会警告后跳过，不能只看索引成功。[JSONL reader]
2. 检查每个输入文档恰好产生一个块，块正文逐字相等，`document_id` 与输入 ID 对齐，token 数符合共同契约。不能只凭配置推断没有再次切分。[建块]
3. **TextUnit ID 不沿用输入 ID**：默认建块代码仅按正文计算 SHA-512。建立 `input_id → text_unit_id → source sidecar` 映射并检查全量 TextUnit ID 唯一；重复正文可能生成重复 ID，而 Local 将块按 ID 放入字典。若发生碰撞，停下并明确采用所有方法一致的多来源/去重策略，不能静默改正文加路径。[建块] [Local builder]
4. 基线复用经过上述核验的实际 `text_units` 和映射；所有方法用同一外部 sidecar 生成评分与展示来源。Sources 中的短 ID 是加载时 DataFrame index，不是文件行号；保存本次短 ID 到实际块 ID 的对应表。[块加载] [来源表]

## 只取 Basic / Local 上下文

`graphrag.api.basic_search(...)`、`graphrag.api.local_search(...)` 是生成答案的 API；没有 `context_only` 参数。它们会完整迭代 streaming 调用，再返回 response/context。仅在回调中收集 context，或只丢弃返回答案，仍然会做 completion。不要调用这两个函数、它们的 streaming 变体或 Search 对象的 `search/stream_search` 来冒充纯检索。[公开查询 API] [Basic 生成器] [Local 生成器]

可用的入口是**固定版本内部 context builder**，两种 `build_context` 都是同步方法；这是后续需要运行验证的集成接口，不能宣称为稳定的公共 context-only API。调用非空 query 时，它们仍会执行同步 embedding，因此“没有生成答案”不等于“没有模型调用”。[Basic builder] [Local builder] [实体映射]

| 方法 | 构造所需对象 | 直接调用 |
| --- | --- | --- |
| `graphrag.query.structured_search.basic_search.basic_context.BasicSearchContext` | `text_embedder`、`text_unit_embeddings`；可传 `text_units`、`tokenizer`、`embedding_vectorstore_key="id"` | `build_context(query, conversation_history=None, k=10, max_context_tokens=12000, context_name="Sources", column_delimiter="\|", text_id_col="id", text_col="text", **kwargs)` |
| `graphrag.query.structured_search.local_search.mixed_context.LocalSearchMixedContext` | `entities`、`entity_text_embeddings`、`text_embedder`；可传 `text_units`、`community_reports`、`relationships`、`covariates`、`tokenizer`、`embedding_vectorstore_key` | 见下列显式调用参数；不依赖构造器备用默认值 |

下面只是供 runner 作者对接的调用片段，`local_builder`、`query` 等须在获准运行后构造；本记录没有执行它：

```python
context = local_builder.build_context(
    query=query,
    conversation_history=None,
    include_entity_names=[],
    exclude_entity_names=[],
    max_context_tokens=12000,
    text_unit_prop=0.5,
    community_prop=0.15,
    top_k_mapped_entities=10,
    top_k_relationships=10,
    include_entity_rank=True,
    include_relationship_weight=True,
    include_community_rank=False,
    use_community_summary=False,
    return_candidate_context=False,
)
```

这些参数与正常工厂传入值对齐；`LocalSearchMixedContext.build_context` 自己的备用默认值是 8000 token / community 0.25，直接调用时必须显式覆盖。`top_k_entities` 是 YAML 字段名，builder 参数叫 `top_k_mapped_entities`。[查询工厂] [Local 配置]

对接顺序：

1. 读取固定运行产物 `text_units`、`entities`、`relationships`、`communities`、`community_reports`，保留原始表及行索引映射。
2. 调用 `graphrag.query.indexer_adapters` 中的 `read_indexer_text_units(text_units)`、`read_indexer_relationships(relationships)`、`read_indexer_entities(entities, communities, community_level)`、`read_indexer_reports(community_reports, communities, community_level)`。`community_level` 是 runner 的显式已记录选择，不是 Local YAML 的字段；claims 关闭可传 `covariates={}`。[索引适配器]
3. 为 Basic 连接 `text_unit_text` 向量索引，为 Local 连接 `entity_description` 索引，使用实际块/实体 ID。官方 `get_embedding_store(config, embedding_name)` 位于 `graphrag.utils.api`，会连接存储；对索引应只读取，不在检索阶段重新 embedding 全语料。[向量连接]
4. 两个 builder 注入同一个已选 embedding 实现，其接口需支持 `embedding(input=[text]).first_embedding`。查询向量与已存向量的模型、维度必须一致。允许运行后可用共享 query-vector 缓存减少重复请求，但须同时记录逻辑调用和实际请求，不改变候选检索算法。[Basic builder] [实体映射]
5. 注入共同的 `o200k_base` tokenizer 以固定比较预算，可使用 `graphrag.tokenizer.get_tokenizer(encoding_model="o200k_base")`。这是检索评估的显式适配：正常查询工厂使用 completion 模型的 tokenizer；它不意味着所选模型的实际计费 token 也按 o200k_base 算。[tokenizer] [查询工厂]
6. 返回 `ContextBuilderResult.context_chunks`（类型声明为字符串或字符串列表）及 `context_records`（表名到 DataFrame）。保存二者原样与额外评分映射；不要接着调用回答模型。若开启 `return_candidate_context=True` 做诊断，Local 表中的 `in_context` 需区分候选与实际进入上下文的行，不能把所有候选算成召回成功。[结果类型] [Local builder]

空候选、空 Sources 表或缺少某种表时，记录为空结果并保留原因；不要调用回答模型补全或伪造来源。多个 context chunk 应逐个保存；供展示合并时保留边界，并重新记录完整展示 token 数。

Basic 用文本相似度结果中的 ID 回收块，最终顺序按已加载 TextUnits 遍历，并非保证向量分数降序。Local 先选实体，再按其来源与邻接组织上下文；默认请求实体候选时有 2 倍 oversampling，关系/原文仍受各自预算裁剪。记录最终上下文，不用配置的 k 代替实际召回数量。[Basic builder] [实体映射] [Local builder]

## Token、调用与可验证范围

`ContextBuilderResult` 的 `llm_calls/prompt_tokens/output_tokens` 默认都是 0；Basic 和 Local 返回时没有把 query embedding 计入这些字段。因此不能据它们声称查询零请求、零 token 或零成本。[结果类型] [Basic builder] [Local builder]

后续 runner 至少分别记录：索引各阶段 completion/embedding；检索逻辑 embedding 调用、实际 endpoint 尝试、失败/重试、缓存命中；provider 返回 usage；共同 tokenizer 计算的输入/上下文 token；每种表的候选数、实际装入数；elapsed time。缺失 usage/cost 写 `unknown`，不能写零。模板开启文件 metrics，但上游默认处理器只在 response 含 usage 时记 token、模型成本表有匹配时才记成本；该记录不能代替 endpoint/重试审计，也不是账单。[Metrics 配置] [Metrics 处理]

目前能做而无需安装微软的是：核对固定源码中的字段、类型、默认值、工作流、调用链，以及用通用 YAML parser 检查语法。**不能**仅凭这些声称已通过 GraphRagConfig/Pydantic 验证、依赖导入、向量后端、embedding 输出、响应格式或实际检索集成。含占位符的模板刻意不能通过正式类型验证；后续还须确定模型/provider、维度、鉴权、tokenizer 资产、Python/依赖版本、community level、重复正文策略与完整预算。此阶段不得执行 context builder，因其非空查询会调用 embedding。

本次实际检查：系统 Ruby/Psych 安全解析 YAML 成功；以 Python 标准库 `ast` 只读解析固定配置源码，17 个配置段的字段名核对通过；30 个固定源码链接的文件和行范围核对通过。以上都不是微软运行时验证。

## 固定官方来源

所有链接固定到相同完整 commit；正文为静态核查或明确标出的集成要求。

[包配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/pyproject.toml#L1-L26
[初始化模板]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/config/init_content.py#L19-L46
[模型配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-llm/graphrag_llm/config/model_config.py#L19-L111
[向量配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-vectors/graphrag_vectors/vector_store_config.py#L12-L58
[总配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/config/models/graph_rag_config.py#L253-L275
[工作流]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/index/workflows/factory.py#L40-L97
[抽取配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/config/models/extract_graph_config.py#L22-L52
[报告配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/config/models/community_reports_config.py#L26-L63
[重试配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-llm/graphrag_llm/config/retry_config.py#L11-L69
[输入配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-input/graphrag_input/input_config.py#L11-L40
[结构化 reader]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-input/graphrag_input/structured_file_reader.py#L32-L65
[块配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-chunking/graphrag_chunking/chunking_config.py#L11-L36
[JSONL reader]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-input/graphrag_input/jsonl.py#L18-L61
[建块]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/index/workflows/create_base_text_units.py#L99-L160
[块加载]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/input/loaders/dfs.py#L225-L257
[来源表]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/context_builder/source_context.py#L21-L79
[公开查询 API]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/api/query.py#L191-L255
[Basic 生成器]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/basic_search/search.py#L59-L110
[Local 生成器]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/local_search/search.py#L56-L106
[Basic builder]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/basic_search/basic_context.py#L30-L109
[Local builder]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/local_search/mixed_context.py#L57-L222
[实体映射]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/context_builder/entity_extraction.py#L41-L96
[查询工厂]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/factory.py#L37-L100
[Local 配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/config/models/local_search_config.py#L11-L49
[索引适配器]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/indexer_adapters.py#L36-L159
[向量连接]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/utils/api.py#L15-L23
[tokenizer]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/tokenizer/get_tokenizer.py#L12-L48
[结果类型]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/context_builder/builders.py#L16-L24
[Metrics 配置]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-llm/graphrag_llm/config/metrics_config.py#L15-L57
[Metrics 处理]: https://github.com/microsoft/graphrag/blob/5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag-llm/graphrag_llm/metrics/default_metrics_processor.py#L73-L130
