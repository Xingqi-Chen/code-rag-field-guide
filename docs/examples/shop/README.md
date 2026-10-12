# 小店调用链：教学示例

这四份原创 Python 文件只用于[报告的原理图解](../../report.md#一先把它想成图书馆和地图)，不属于 Requests／Click 语料，也不进入实验。

调用关系是：[`checkout.place_order`](checkout.py) → [`orders.confirm_order`](orders.py) → [`mailer.make_receipt`](mailer.py)。另一个 [`analytics.order_count`](analytics.py) 也谈订单，却没有被这条链调用。

示例只返回回执数据，没有支付、库存、持久化或发信行为；函数名“确认”仅用于说明分工。省略了输入校验与真实业务规则，不是生产商店实现。
