from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KnrOpportunity(models.Model):
    _name = "knr.opportunity"
    _description = "Peluang Pesanan Institusi"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "followup_date, id desc"

    name = fields.Char(string="Nama Peluang", required=True, tracking=True)
    client_id = fields.Many2one("knr.client", string="Klien Institusi", required=True)
    need_description = fields.Text(string="Kebutuhan Klien")
    expected_value = fields.Monetary(string="Perkiraan Nilai")
    expected_datetime = fields.Datetime(string="Perkiraan Waktu Pesanan")
    stage = fields.Selection([("new", "Baru"), ("offered", "Ditawarkan"), ("agreed", "Disepakati"), ("lost", "Batal")], default="new", tracking=True, required=True)
    interaction_notes = fields.Text(string="Catatan Interaksi")
    followup_plan = fields.Text(string="Rencana Tindak Lanjut")
    followup_date = fields.Date(string="Tenggat Tindak Lanjut")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    order_id = fields.Many2one("knr.order", string="Pesanan yang Dibuat", readonly=True)

    def action_create_order(self):
        self.ensure_one()
        if self.stage != "agreed":
            raise UserError(_("Peluang harus berstatus Disepakati sebelum dibuat menjadi pesanan."))
        action = self.env.ref("knr_order.action_knr_order_new").read()[0]
        action["context"] = {"default_client_id": self.client_id.id}
        return action

    @api.model
    def get_followup_reminders(self):
        today = fields.Date.context_today(self)
        return self.search([("followup_date", "<=", today), ("stage", "not in", ["agreed", "lost"])])
