"""原创教学代码：演示跨文件调用，不实现真实订单确认规则。"""
from mailer import make_receipt


def confirm_order(order):
    """返回教学回执数据。"""
    return make_receipt(order)
