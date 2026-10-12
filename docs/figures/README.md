# Microsoft GraphRAG 原理图

四张图为本项目原创教学示意，**不是系统实测截图或性能结果**。正文用 PNG，避免读者设备缺少中文字体；SVG 保留可编辑文字及无障碍标题／描述。每张图在正文均有 alt 文本和文字解释。

| 内容 | PNG | SVG |
| --- | --- | --- |
| 索引证据与下游开发工具的分工 | [预览](01-code-evidence-layer.png) | [编辑源](01-code-evidence-layer.svg) |
| 小 feature 的函数、调用者、测试与约定 | [预览](02-feature-context.png) | [编辑源](02-feature-context.svg) |
| 符号身份与更新新鲜度 | [预览](03-identity-and-freshness.png) | [编辑源](03-identity-and-freshness.svg) |
| 默认、提示词定制、外接程序图 | [预览](04-three-variants.png) | [编辑源](04-three-variants.svg) |

统一编辑[生成脚本](../../scripts/generate_principle_figures.py)，再生成两种格式。脚本仅依赖 [Pillow](../../requirements-figures.txt)，不调用模型或网络服务：

```bash
python3 -m venv .venv-figures
.venv-figures/bin/python -m pip install -r requirements-figures.txt
.venv-figures/bin/python scripts/generate_principle_figures.py --preview
# 如未找到中文字体，显式指定本地已获使用权的字体：
.venv-figures/bin/python scripts/generate_principle_figures.py --font /path/to/CJK-font.ttf --preview
```

Mac mini 本次使用系统 Hiragino Sans GB。生成源还支持本地 Noto Sans CJK；字体不复制入库。SVG 宽 760 单位，PNG 宽 1520 像素。手机预览宽 390 像素，保存在忽略目录 `.cache/figure-previews/`。不同字体或 Pillow 版本可能改变字形与 PNG 字节，需重新目视检查。

两种格式由相同几何与文字定义输出，PNG 由 Pillow 直接绘制。SVG 结构检查不等于所有浏览器的视觉保证；本次视觉验收针对正文实际展示的 PNG 和手机预览，未声明完成整页 SVG 浏览器渲染验证。
