# 原理图与维护方法

四张图是原创教学示意，不是额外实验结果。报告以 PNG 展示，避免读者设备缺少中文字体；SVG 保留可编辑文字及无障碍标题／描述。正文也给出完整文字说明和图片 alt 文本。

| 图 | PNG 预览 | 可编辑 SVG |
| --- | --- | --- |
| 普通检索与关系查找 | [01](01-search-and-relations.png) | [01](01-search-and-relations.svg) |
| 建图到回答的五步 | [02](02-five-steps.png) | [02](02-five-steps.svg) |
| 错边、遗漏、噪声与预算 | [03](03-failures-and-budget.png) | [03](03-failures-and-budget.svg) |
| 两种不同的图 | [04](04-two-kinds-of-graph.png) | [04](04-two-kinds-of-graph.svg) |

统一修改[生成脚本](../../scripts/generate_principle_figures.py)，再重新生成，避免手工改图后两种格式分歧：

```bash
.venv/bin/python scripts/generate_principle_figures.py --preview
# 其他机器可指定已安装且有使用权的中文字体：
.venv/bin/python scripts/generate_principle_figures.py --font /path/to/CJK-font.ttf --preview
```

依赖只有实验环境已有的 Pillow（见[锁定依赖](../../requirements.lock.txt)）。本次使用 Mac mini 系统的 Hiragino Sans GB；不将字体文件入库。Linux 可用本地 Noto Sans CJK。字体和 Pillow 版本不同可能改变字形、换行空间及 PNG 字节，生成后仍须目视检查。

SVG 画布宽 760 单位；PNG 宽 1520 像素，均为纵向布局。`--preview` 另生成 390 像素宽的手机预览，保存在忽略目录 `.cache/figure-previews/`，不上传缓存。PNG 与 SVG 来自相同的文字、位置和箭头定义，PNG 由 Pillow 直接渲染；不是宣称两个渲染器输出逐像素一致。

检查正文、SVG 渲染及手机 PNG：中文应完整，箭头不压字，说明不越界。生成脚本检查文字画布边界；发布快检还检查 PNG 校验和及尺寸、SVG 基本结构、成对文件、相对链接和 alt 文本。自动检查不能取代目视检查。
