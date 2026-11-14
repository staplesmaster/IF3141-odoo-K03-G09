from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class KnrClient(models.Model):
    _name = "knr.client"
    _description = "Klien Institusi"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Nama Institusi", required=True, tracking=True)
    contact_name = fields.Char(string="Nama Narahubung", required=True)
    phone = fields.Char(string="Nomor Kontak", required=True)
    email = fields.Char(string="Email")
    address = fields.Text(string="Alamat")
    partnership = fields.Selection([("partner", "Mitra"), ("regular", "Non-mitra")], default="regular", required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    order_ids = fields.One2many("knr.order", "client_id", string="Riwayat Pesanan")
    order_count = fields.Integer(compute="_compute_order_count")

    @api.depends("order_ids")
    def _compute_order_count(self):
        for rec in self:
            rec.order_count = len(rec.order_ids)

    @api.onchange("name", "phone")
    def _onchange_possible_duplicate(self):
        for rec in self:
            if rec.name or rec.phone:
                domain = [("id", "!=", rec._origin.id or 0), ("active", "=", True)]
                conditions = []
                if rec.name:
                    conditions.append(("name", "ilike", rec.name))
                if rec.phone:
                    conditions.append(("phone", "=", rec.phone))
                if len(conditions) == 2:
                    domain += ["|"] + conditions
                elif conditions:
                    domain += conditions
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    return {"warning": {"title": _("Kemungkinan Duplikasi"), "message": _("Klien dengan nama atau nomor kontak serupa sudah tersedia: %s") % duplicate.name}}

    def action_view_orders(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Riwayat Pesanan", "res_model": "knr.order", "view_mode": "tree,form", "domain": [("client_id", "=", self.id)]}


class KnrProduct(models.Model):
    _name = "knr.product"
    _description = "Produk dan Paket"
    _inherit = ["mail.thread"]
    _order = "category, name"

    name = fields.Char(required=True, tracking=True)
    category = fields.Selection([("snack", "Snack Box"), ("catering", "Catering")], required=True, default="snack", tracking=True)
    uom = fields.Char(string="Satuan", default="Porsi", required=True)
    price = fields.Monetary(string="Harga Jual", required=True, default=0)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, required=True)
    department = fields.Selection([("bakery", "Bakery"), ("kitchen", "Dapur Saji")], required=True)
    description = fields.Text(string="Keterangan")
    active = fields.Boolean(default=True)

    _sql_constraints = [("name_category_unique", "unique(name, category)", "Nama produk sudah digunakan dalam kategori tersebut.")]


class KnrShippingConfig(models.Model):
    _name = "knr.shipping.config"
    _description = "Ketentuan Ongkos Kirim"

    name = fields.Char(default="Ketentuan Ongkos Kirim", required=True)
    rate_per_km = fields.Monetary(string="Tarif per Kilometer", required=True, default=0)
    free_distance_km = fields.Float(string="Batas Jarak Gratis (km)", required=True, default=0)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True)

    @api.constrains("rate_per_km", "free_distance_km")
    def _check_nonnegative(self):
        for rec in self:
            if rec.rate_per_km < 0 or rec.free_distance_km < 0:
                raise ValidationError(_("Tarif dan batas jarak tidak boleh negatif."))
