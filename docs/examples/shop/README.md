# 小店调用链：教学示例

这四份原创 Python 文件只用于[新版报告](../../report.md)解释“把代码当作文本交给 Microsoft GraphRAG 会发生什么”。本轮没有运行模型；它们不是评测集，文中的实体卡片与推断只是教学假设，不是微软系统的真实输出。

调用关系是：[`checkout.place_order`](checkout.py) → [`orders.confirm_order`](orders.py) → [`mailer.make_receipt`](mailer.py)。另一个 [`analytics.order_count`](analytics.py) 也谈订单，却没有被这条链调用。

示例只返回回执数据，没有支付、库存、持久化或发信行为；函数名“确认”仅用于说明分工。省略了输入校验与真实业务规则，不是生产商店实现。
