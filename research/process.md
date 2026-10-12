# 研究过程与复核方法

研究日：2026-10-12，执行地点为用户指定的 Mac mini。本次聚焦 **Microsoft GraphRAG 的代码索引／上下文检索能力**。模型生成和 embedding 调用均为 0；没有执行下载仓库中的程序，没有触及其他项目。

## 当前修订做了什么

- 先以提交 `ad34d1c` 修订[研究计划](plan.md)，把精确定位、真实调用、修改影响、feature 上下文作为四项主任务；社区导读降为机制背景。
- 分别补查[固定源码](implementation.md)与[直接效果证据](direct-evidence.md)。源码新增数据模型、位置来源、符号身份、更新合并、缓存与 BYOG 边界；文献补检新增微软维护者确认的 code4llm 代码研究线索，未将其归作公开包的已验证效果。
- 保持微软 v3.3.0、commit `5faaaf4f5685fa2056fa8c3bf9342cb089f2942f`。78 个引用文件的 SHA-256、大小、行数与引用范围见[清单](microsoft-version.json)；第三方源码只放在忽略缓存中。
- 重写 README、主文、四张图与[必要验证计划](pilot-decision.md)。用原创小店的待做 feature 说明函数、调用者、规范、测试和干扰材料；feature 尚未实现，没有把手工成果当微软输出。
- 原来的源码研究和最早自制代码图实验都保留于[正常 Git 历史](legacy.md)。不改写历史，不 force push。

## 环境与执行边界

机器硬件沿用本任务已记录环境：Apple M4、10 CPU、16 GiB 内存；见[历史环境清单](https://github.com/Xingqi-Chen/code-rag-field-guide/blob/ce5d4c6cc78253fd7d70b27fb71e467ac9d38141/results/environment.json)。系统为 macOS 26.4.1（25E253）、arm64。

源码字节检查使用 Python 3.14.5；最终发布测试和绘图使用现有隔离环境 Python 3.12.10，绘图依赖 Pillow 12.3.0。检查脚本支持 3.14 不代表微软包支持它：固定版声明 Python >=3.11,<3.14，本轮未安装其依赖。CI 用 Python 3.12 跑发布检查和两个原创教学测试，无模型或长实验。

公开内容不含权重、向量库、第三方完整源码、缓存、凭据或私人路径。第三方来源以链接及简要转述归因；[NOTICE](../NOTICE.md)说明许可边界。

## 可复核命令与真实日志

已有源码缓存时，只做静态字节核对：

```bash
python3 scripts/check_source.py
```

新 clone 可先运行 `python3 scripts/check_source.py --fetch`，从官方固定 commit raw URL 下载缺失引用文件到 `.cache/`。不解压、导入或执行第三方代码；只核对哈希、字节、行数与引用范围，不能自动证明文字解释正确。[本次源码检查输出](../logs/source-check.log)记录实际文件数。

发布检查与教学基线检查：

```bash
python3 -m unittest discover -s tests
python3 scripts/validate.py
# 从仓库根目录进入原创教学代码目录：
cd docs/examples/shop
python3 -m unittest test_shop
```

两项教学测试检查旧入口默认回执和不修改订单的契约，**不测试新 feature，不是 GraphRAG 效果实验**。结果与发布检查输出保存在[真实日志](../logs/publication-checks.log)。

发布检查覆盖相对链接／锚点、四对图像的结构及尺寸、PNG 元数据和 CRC、SVG 无主动内容及无障碍字段、文件大小、常见路径／密钥模式，以及旧实验目录未混回当前版本。这不保证所有外链永久可读或能发现所有秘密。

## 图文与独立复核

四图来自[同一生成脚本](../scripts/generate_principle_figures.py)，PNG 为 2 倍尺寸，手机预览宽 390 像素，制作方法见[配图说明](../docs/figures/README.md)。完整图和手机图逐张检查文字、框、箭头与阅读顺序。视觉验收针对正文使用的 PNG；SVG 做结构检查，本轮没有浏览器 SVG 渲染验收的宣称。

本次由两位未参与稿件编写的独立审阅者分别核查技术事实和非技术可读性。技术复核再次核对 78 个源文件及身份、引用、Local、更新、BYOG 与官方 #1779；没有发现阻断性事实错误，但未重做完整文献检索或运行微软流程。图文复核阅读当前主文和小店代码，检查四张完整 PNG 及对应 390 像素预览；没有截断、遮挡或箭头压字，未替代浏览器整页验收。

| 审阅建议 | 本次处理 |
| --- | --- |
| 试点原来只明确 Basic／Local 同 embedding，未覆盖 hybrid | 改成三组向量部分共用；不同生产模型另列系统级比较 |
| 图中 title／update 及 feature 英文增加负担 | 改用文档标题、标准更新、新功能，首次说明 feature |
| “删除文件未清除”可能不清楚清除对象 | 明确是源码删除后默认路径不清除旧索引记录 |
| “编译器语义”“数据契约”不够直观 | 图中改为函数身份与调用校验、输入格式与字段含义 |

文字调整后重新生成并目视检查受影响图片，再运行发布检查。前一版的审阅没有被当作本次复核。实际检索效果、索引同步效果与新功能实现成功率仍未验证。

## 发布核验

使用项目专用 Git 作者名，正常新增提交并 push。发布后核对 public、remote HEAD、该 SHA 对应 CI，以及匿名可读的 README、报告和 PNG/SVG；最终 SHA 与 CI 链接随交付提供，避免同一提交自引用。未启动模型实验不阻塞文献研究版发布。
