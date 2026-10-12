"""原创教学代码：仅生成数据，不发送邮件。"""


def make_receipt(order):
    return {"to": order["email"], "subject": "订单回执"}
