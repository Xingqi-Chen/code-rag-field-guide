"""Baseline contracts for the original teaching fixture, not a GraphRAG evaluation."""
import unittest
from checkout import place_order


class ExistingOrderContract(unittest.TestCase):
    def test_existing_caller_keeps_default_receipt(self):
        order = {"email": "buyer@example.test"}
        self.assertEqual(place_order(order),
                         {"to": "buyer@example.test", "subject": "订单回执"})

    def test_order_input_is_not_mutated(self):
        order = {"email": "buyer@example.test", "items": ["book"]}
        before = {"email": "buyer@example.test", "items": ["book"]}
        place_order(order)
        self.assertEqual(order, before)


if __name__ == '__main__':
    unittest.main()
