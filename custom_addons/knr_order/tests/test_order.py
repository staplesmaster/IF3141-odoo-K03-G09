from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestKnrOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env["knr.client"].create({
            "name": "Institusi Uji KNR", "contact_name": "Narahubung",
            "phone": "081234567890", "address": "Bandung",
        })
        cls.product = cls.env["knr.product"].create({
            "name": "Snack Box Uji", "category": "snack", "uom": "box",
            "price": 25000, "department": "bakery",
        })
        cls.env.user.write({"groups_id": [(4, cls.env.ref("knr_order.group_knr_bakery").id)]})
        cls.order = cls.env["knr.order"].create({
            "client_id": cls.client.id,
            "service_datetime": "2026-12-01 03:00:00",
            "delivery_address": "Bandung",
            "line_ids": [(0, 0, {"product_id": cls.product.id, "quantity": 10, "unit_price": 25000})],
        })

    def test_order_number_and_initial_state(self):
        self.assertNotEqual(self.order.name, "New")
        self.assertEqual(self.order.state, "received")
        self.assertEqual(len(self.order.capacity_ids), 1)

    def test_production_requires_capacity(self):
        with self.assertRaises(UserError):
            self.order.with_context(knr_state_transition=True).action_start_production()

    def test_state_cannot_be_changed_directly(self):
        with self.assertRaises(UserError):
            self.order.write({"state": "produced"})
