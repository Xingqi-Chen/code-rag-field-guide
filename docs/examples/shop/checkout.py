"""原创教学代码：下单入口；不执行真实支付或发信。"""
from orders import confirm_order


def place_order(order):
    """把教学订单交给确认函数。"""
    return confirm_order(order)
