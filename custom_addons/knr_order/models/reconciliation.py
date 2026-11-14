from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KnrReconciliation(models.Model):
    _name = "knr.reconciliation"
    _description = "Pencocokan Pembayaran POS CSA"
    _inherit = ["mail.thread"]
    _order = "service_datetime desc"

    order_id = fields.Many2one("knr.order", string="Nomor Pesanan", required=True, ondelete="restrict")
    client_id = fields.Many2one(related="order_id.client_id", store=True)
    service_datetime = fields.Datetime(related="order_id.service_datetime", store=True)
    order_total = fields.Monetary(related="order_id.total", store=True)
    result = fields.Selection([("pending", "Belum Dicocokkan"), ("matched", "Sesuai"), ("difference", "Selisih")], default="pending", required=True, tracking=True)
    notes = fields.Text(string="Catatan Tindak Lanjut")
    checked_by = fields.Many2one("res.users", readonly=True)
    checked_at = fields.Datetime(readonly=True)
    currency_id = fields.Many2one(related="order_id.currency_id")

    _sql_constraints = [("order_reconcile_unique", "unique(order_id)", "Setiap pesanan hanya memiliki satu catatan pencocokan.")]

    def write(self, vals):
        if "result" in vals and not self.env.context.get("knr_reconcile_action"):
            raise UserError(_("Hasil pencocokan hanya dapat diubah melalui tombol hasil pencocokan."))
        return super().write(vals)

    def action_mark_matched(self):
        self._mark("matched")

    def action_mark_difference(self):
        self._mark("difference")

    def _mark(self, result):
        if not self.env.user.has_group("knr_order.group_knr_admin"):
            raise UserError(_("Hanya Kepala Administrasi yang dapat mencatat hasil pencocokan."))
        for rec in self:
            if result == "difference" and not rec.notes:
                raise UserError(_("Catatan tindak lanjut wajib diisi jika terdapat selisih."))
            rec.with_context(knr_reconcile_action=True).write({"result": result, "checked_by": self.env.user.id, "checked_at": fields.Datetime.now()})
            rec.order_id.sudo().write({"reconciliation_state": result})
