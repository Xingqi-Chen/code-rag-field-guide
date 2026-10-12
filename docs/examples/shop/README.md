# 小 feature 需要哪些代码证据：教学示例

这个原创小店只用于[报告](../../report.md)说明开发助手需要怎样的索引证据。本轮没有运行微软模型；代码和图不是 GraphRAG 评测集或输出。

调用关系是：[`checkout.place_order`](checkout.py) → [`orders.confirm_order`](orders.py) → [`mailer.make_receipt`](mailer.py)。另一个 [`analytics.order_count`](analytics.py) 也谈订单，却没有被这条链调用。

示例只返回回执数据，没有支付、库存、持久化或发信行为；函数名“确认”仅用于说明分工。省略了输入校验与真实业务规则，不是生产商店实现。

## 待做 feature

允许调用者从下单入口指定回执主题，未指定时仍使用“订单回执”。**本仓库保留 feature 实现前的代码**，没有把手工改动冒充 GraphRAG 生成成果。

| 应找出的材料 | 为什么需要 |
| --- | --- |
| [mailer.make_receipt](mailer.py) | 目前回执主题在这里形成 |
| [orders.confirm_order](orders.py)、[checkout.place_order](checkout.py) | 调用方向与参数传递需要核对；只改最末端不等于入口能使用新功能 |
| [现有测试](test_shop.py) | 保住旧入口、默认主题和不修改订单的约定；测试代码也属于需要检索的语料 |
| [教学约定](CONVENTIONS.md) | 避免把“回执”扩写成真实发信，并保持兼容 |
| [analytics.order_count](analytics.py) | 同样提到订单，但不是本例待改链路；把它列为必须修改是误报 |

未来还需添加“自定义主题从入口传到回执”的验收测试。新增测试通过也不等于所有改动正确，仍应检查补丁与约定。这里只能说明**哪些证据有用**，不能证明任何索引方法已经找到了它们。

只运行原创教学代码的现有检查，无外部依赖、模型或网络：

```bash
cd docs/examples/shop
python3 -m unittest test_shop
```
