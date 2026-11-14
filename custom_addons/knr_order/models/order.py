from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError, ValidationError


class KnrOrder(models.Model):
    _name = "knr.order"
    _description = "Pesanan Institusi"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "service_datetime desc, id desc"

    name = fields.Char(string="Nomor Pesanan", required=True, copy=False, readonly=True, default="New", tracking=True)
    client_id = fields.Many2one("knr.client", string="Klien Institusi", required=True, tracking=True, domain=[("active", "=", True)])
    line_ids = fields.One2many("knr.order.line", "order_id", string="Produk Pesanan", copy=True)
    service_datetime = fields.Datetime(string="Tanggal dan Jam Layanan", required=True, tracking=True)
    delivery_address = fields.Text(string="Alamat Tujuan", required=True)
    distance_km = fields.Float(string="Jarak Pengiriman (km)", required=True, default=0)
    shipping_fee = fields.Monetary(string="Ongkos Kirim", compute="_compute_amounts", store=True, tracking=True)
    shipping_basis = fields.Char(string="Dasar Ongkos Kirim", compute="_compute_amounts", store=True)
    manual_shipping = fields.Boolean(string="Penyesuaian Manual")
    manual_shipping_amount = fields.Monetary(string="Ongkos Kirim Manual")
    change_reason = fields.Char(string="Alasan Perubahan", copy=False)
    manual_shipping_reason = fields.Char(string="Alasan Penyesuaian Ongkir")
    special_notes = fields.Text(string="Catatan Khusus")
    temporary_form_no = fields.Char(string="Nomor Formulir Sementara", copy=False)
    received_at = fields.Datetime(string="Waktu Penerimaan", default=fields.Datetime.now, readonly=True)
    recorder_id = fields.Many2one("res.users", string="Pencatat", default=lambda self: self.env.user, readonly=True)
    state = fields.Selection([
        ("received", "Diterima"), ("capacity", "Kapasitas Dikonfirmasi"),
        ("produced", "Diproduksi"), ("sent", "Dikirim"),
        ("done", "Selesai"), ("cancel", "Dibatalkan")], default="received", required=True, tracking=True)
    subtotal = fields.Monetary(compute="_compute_amounts", store=True)
    total = fields.Monetary(compute="_compute_amounts", store=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    capacity_ids = fields.One2many("knr.capacity", "order_id", string="Konfirmasi Kapasitas")
    history_ids = fields.One2many("knr.order.history", "order_id", string="Riwayat Perubahan")
    cancellation_reason = fields.Text(string="Alasan Pembatalan", tracking=True)
    delivery_datetime = fields.Datetime(string="Waktu Dikirim")
    completion_datetime = fields.Datetime(string="Waktu Selesai")
    reconciliation_state = fields.Selection([("pending", "Belum Dicocokkan"), ("matched", "Sesuai"), ("difference", "Selisih")], default="pending", string="Pencocokan Pembayaran", tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("knr.order") or "New"
        records = super().create(vals_list)
        for rec in records:
            rec._create_capacity_rows()
            rec.message_post(body=_("Pesanan dibuat dengan status Diterima."))
        return records

    def _create_capacity_rows(self):
        self._sync_capacity_rows()

    def _sync_capacity_rows(self, reset=False):
        for order in self:
            departments = set(order.line_ids.mapped("product_id.department"))
            for capacity in order.capacity_ids:
                if capacity.department not in departments:
                    capacity.sudo().unlink()
                elif reset:
                    capacity.sudo().with_context(knr_capacity_action=True).write({"decision": "pending", "reason": False, "confirmed_by": False, "confirmed_at": False})
            for dept in departments:
                if not order.capacity_ids.filtered(lambda c: c.department == dept):
                    self.env["knr.capacity"].sudo().create({"order_id": order.id, "department": dept})

    @api.depends("line_ids.subtotal", "distance_km", "client_id.partnership", "manual_shipping", "manual_shipping_amount")
    def _compute_amounts(self):
        config = self.env["knr.shipping.config"].search([("active", "=", True)], limit=1, order="id desc")
        for order in self:
            order.subtotal = sum(order.line_ids.mapped("subtotal"))
            if order.manual_shipping:
                fee = order.manual_shipping_amount
                basis = "Penyesuaian manual oleh pengguna berwenang"
            elif order.client_id.partnership == "partner":
                fee, basis = 0, "Gratis - klien mitra"
            elif config and order.distance_km <= config.free_distance_km:
                fee, basis = 0, "Gratis - dalam batas jarak"
            elif config:
                fee, basis = config.rate_per_km * order.distance_km, "Tarif per km x jarak"
            else:
                fee, basis = 0, "Ketentuan ongkos kirim belum diatur"
            order.shipping_fee = fee
            order.shipping_basis = basis
            order.total = order.subtotal + fee

    @api.constrains("manual_shipping", "manual_shipping_amount", "manual_shipping_reason")
    def _check_manual_shipping(self):
        for order in self:
            if order.manual_shipping and (order.manual_shipping_amount < 0 or not order.manual_shipping_reason):
                raise ValidationError(_("Ongkos kirim manual harus bernilai tidak negatif dan memiliki alasan."))

    @api.constrains("line_ids", "distance_km", "temporary_form_no")
    def _check_order_data(self):
        for order in self:
            if order.distance_km < 0:
                raise ValidationError(_("Jarak pengiriman tidak boleh negatif."))
            if not order.line_ids:
                raise ValidationError(_("Pesanan harus memiliki minimal satu produk."))
            if order.temporary_form_no:
                duplicate = self.search([("id", "!=", order.id), ("temporary_form_no", "=", order.temporary_form_no)], limit=1)
                if duplicate:
                    raise ValidationError(_("Nomor formulir sementara sudah pernah digunakan."))

    def write(self, vals):
        if "state" in vals and not self.env.context.get("knr_state_transition"):
            raise UserError(_("Status pesanan hanya dapat diubah melalui tombol proses yang sesuai."))
        shipping_fields = {"manual_shipping", "manual_shipping_amount", "manual_shipping_reason"}
        if shipping_fields.intersection(vals) and not (self.env.user.has_group("knr_order.group_knr_admin") or self.env.user.has_group("knr_order.group_knr_authorized")):
            raise AccessError(_("Anda tidak berwenang menyesuaikan ongkos kirim."))
        if self.env.user.has_group("knr_order.group_knr_authorized") and not self.env.user.has_group("knr_order.group_knr_controller") and set(vals) - shipping_fields:
            raise AccessError(_("Pengguna Berwenang hanya dapat menyesuaikan ongkos kirim."))
        if self.env.user.has_group("knr_order.group_knr_admin") and not self.env.user.has_group("knr_order.group_knr_controller") and set(vals) - shipping_fields:
            raise AccessError(_("Kepala Administrasi hanya dapat mengubah informasi ongkos kirim pada pesanan."))
        tracked = {"client_id", "line_ids", "service_datetime", "delivery_address", "distance_km", "special_notes"}
        if tracked.intersection(vals) and not self.env.user.has_group("knr_order.group_knr_controller"):
            raise AccessError(_("Hanya Controller atau Petugas Pengganti yang dapat mengubah rincian pesanan."))
        if tracked.intersection(vals):
            for order in self:
                if order.state in ("done", "cancel"):
                    raise UserError(_("Pesanan selesai atau dibatalkan tidak dapat diubah."))
                if not vals.get("change_reason"):
                    raise UserError(_("Alasan perubahan pesanan wajib diisi."))
                old_state = order.state
                old_values = {key: order[key] for key in tracked if key in order._fields and key != "line_ids"}
                result = super(KnrOrder, order).write(vals)
                reason = vals.get("change_reason") or "Perubahan rincian pesanan"
                self.env["knr.order.history"].sudo().create({"order_id": order.id, "description": reason, "changed_by": self.env.user.id, "old_summary": str(old_values), "new_summary": str({k: vals.get(k) for k in vals if k in tracked})})
                order.write({"change_reason": False})
                if "line_ids" in vals:
                    order._sync_capacity_rows(reset=True)
                if old_state in ("capacity", "produced", "sent") and ("line_ids" in vals or "service_datetime" in vals):
                    order._set_state("received")
                    order._sync_capacity_rows(reset=True)
                order.message_post(body=_("Rincian pesanan diperbarui. %s") % reason)
            return True
        return super().write(vals)

    def _set_state(self, new_state, extra_vals=None):
        for order in self:
            vals = dict(extra_vals or {})
            vals["state"] = new_state
            order.with_context(knr_state_transition=True).write(vals)

    def _update_capacity_state(self):
        for order in self:
            if order.capacity_ids and all(c.decision == "yes" for c in order.capacity_ids):
                order._set_state("capacity")

    def action_reset_capacity(self):
        if not self.env.user.has_group("knr_order.group_knr_controller"):
            raise AccessError(_("Hanya Controller yang dapat meminta konfirmasi ulang."))
        for order in self:
            if order.state != "received":
                raise UserError(_("Konfirmasi ulang hanya dapat diminta saat status Diterima."))
            order._sync_capacity_rows(reset=True)
            order.message_post(body=_("Konfirmasi kapasitas diminta ulang oleh %s.") % self.env.user.name)

    def action_start_production(self):
        for order in self:
            if not self.env.user.has_group("knr_order.group_knr_bakery") and not self.env.user.has_group("knr_order.group_knr_kitchen"):
                raise AccessError(_("Hanya bagian produksi yang dapat memperbarui status produksi."))
            if order.state != "capacity" or any(c.decision != "yes" for c in order.capacity_ids):
                raise UserError(_("Pesanan belum memiliki konfirmasi kapasitas lengkap."))
            order._set_state("produced")

    def action_mark_sent(self):
        if not self.env.user.has_group("knr_order.group_knr_delivery"):
            raise AccessError(_("Hanya Petugas Pengiriman yang dapat memperbarui status pengiriman."))
        for order in self:
            if order.state != "produced":
                raise UserError(_("Pesanan harus berstatus Diproduksi sebelum Dikirim."))
            order._set_state("sent", {"delivery_datetime": fields.Datetime.now()})

    def action_mark_done(self):
        if not self.env.user.has_group("knr_order.group_knr_delivery"):
            raise AccessError(_("Hanya Petugas Pengiriman yang dapat menyelesaikan pesanan."))
        for order in self:
            if order.state != "sent":
                raise UserError(_("Pesanan harus berstatus Dikirim sebelum Selesai."))
            order._set_state("done", {"completion_datetime": fields.Datetime.now()})

    def action_cancel_order(self):
        for order in self:
            if not self.env.user.has_group("knr_order.group_knr_controller"):
                raise AccessError(_("Hanya Controller atau Petugas Pengganti yang dapat membatalkan pesanan."))
            if order.state in ("done", "cancel"):
                raise UserError(_("Pesanan selesai atau dibatalkan tidak dapat dibatalkan kembali."))
            if not order.cancellation_reason:
                raise UserError(_("Alasan pembatalan wajib diisi."))
            order._set_state("cancel")
            order.message_post(body=_("Pesanan dibatalkan. Alasan: %s") % order.cancellation_reason)

    def action_create_reconciliation(self):
        self.ensure_one()
        if not self.env.user.has_group("knr_order.group_knr_admin"):
            raise AccessError(_("Hanya Kepala Administrasi yang dapat membuat rekap pencocokan."))
        existing = self.env["knr.reconciliation"].search([("order_id", "=", self.id)], limit=1)
        if existing:
            rec = existing
        else:
            rec = self.env["knr.reconciliation"].create({"order_id": self.id})
        return {"type": "ir.actions.act_window", "res_model": "knr.reconciliation", "view_mode": "form", "res_id": rec.id}

    def action_copy_order(self):
        self.ensure_one()
        if not self.env.user.has_group("knr_order.group_knr_controller"):
            raise AccessError(_("Hanya Controller atau Petugas Pengganti yang dapat menyalin pesanan."))
        vals = self.copy_data({"state": "received", "name": "New", "temporary_form_no": False, "capacity_ids": [(5, 0, 0)], "history_ids": [(5, 0, 0)]})[0]
        new_order = self.create(vals)
        return {"type": "ir.actions.act_window", "res_model": "knr.order", "view_mode": "form", "res_id": new_order.id}

    def action_set_manual_shipping(self):
        if not (self.env.user.has_group("knr_order.group_knr_admin") or self.env.user.has_group("knr_order.group_knr_authorized")):
            raise AccessError(_("Penyesuaian ongkos kirim hanya untuk pengguna berwenang."))
        for order in self:
            if not order.manual_shipping_reason:
                raise UserError(_("Alasan penyesuaian ongkos kirim wajib diisi."))
            order.message_post(body=_("Ongkos kirim disesuaikan manual. Alasan: %s") % order.manual_shipping_reason)


class KnrOrderLine(models.Model):
    _name = "knr.order.line"
    _description = "Baris Pesanan"

    order_id = fields.Many2one("knr.order", required=True, ondelete="cascade")
    product_id = fields.Many2one("knr.product", required=True, domain=[("active", "=", True)])
    description = fields.Text(related="product_id.description", readonly=True)
    quantity = fields.Float(required=True, default=1)
    unit_price = fields.Monetary(required=True)
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True)
    department = fields.Selection(related="product_id.department", store=True)
    currency_id = fields.Many2one(related="order_id.currency_id", store=True)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.price

    @api.depends("quantity", "unit_price")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price

    @api.constrains("quantity", "unit_price")
    def _check_values(self):
        for line in self:
            if line.quantity <= 0 or line.unit_price < 0:
                raise ValidationError(_("Jumlah harus lebih dari nol dan harga tidak boleh negatif."))


class KnrCapacity(models.Model):
    _name = "knr.capacity"
    _description = "Konfirmasi Kapasitas Produksi"
    _inherit = ["mail.thread"]
    _order = "id"

    order_id = fields.Many2one("knr.order", required=True, ondelete="cascade")
    department = fields.Selection([("bakery", "Bakery"), ("kitchen", "Dapur Saji")], required=True, tracking=True)
    decision = fields.Selection([("pending", "Menunggu"), ("yes", "Sanggup"), ("no", "Tidak Sanggup")], default="pending", required=True, tracking=True)
    reason = fields.Text(string="Alasan jika tidak sanggup")
    confirmed_by = fields.Many2one("res.users", readonly=True)
    confirmed_at = fields.Datetime(readonly=True)

    def write(self, vals):
        protected = {"decision", "reason", "confirmed_by", "confirmed_at"}
        if protected.intersection(vals) and not self.env.context.get("knr_capacity_action"):
            raise UserError(_("Keputusan kapasitas hanya dapat diubah melalui tombol Sanggup/Tidak Sanggup."))
        return super().write(vals)

    def action_confirm_yes(self):
        self._check_department_access()
        for rec in self:
            rec.with_context(knr_capacity_action=True).write({"decision": "yes", "confirmed_by": self.env.user.id, "confirmed_at": fields.Datetime.now(), "reason": False})
            rec.order_id.message_post(body=_("%s menyatakan SANGGUP untuk pesanan %s.") % (dict(rec._fields["department"].selection).get(rec.department), rec.order_id.name))
            rec.order_id._update_capacity_state()

    def action_confirm_no(self):
        self._check_department_access()
        for rec in self:
            if not rec.reason:
                raise UserError(_("Alasan ketidaksanggupan wajib diisi."))
            rec.with_context(knr_capacity_action=True).write({"decision": "no", "confirmed_by": self.env.user.id, "confirmed_at": fields.Datetime.now()})
            rec.order_id._set_state("received")
            rec.order_id.message_post(body=_("Kapasitas %s tidak sanggup: %s") % (rec.department, rec.reason))

    def _check_department_access(self):
        for rec in self:
            allowed = (rec.department == "bakery" and self.env.user.has_group("knr_order.group_knr_bakery")) or (rec.department == "kitchen" and self.env.user.has_group("knr_order.group_knr_kitchen"))
            if not allowed:
                raise AccessError(_("Anda tidak berwenang mengonfirmasi kapasitas bagian ini."))


class KnrOrderHistory(models.Model):
    _name = "knr.order.history"
    _description = "Riwayat Perubahan Pesanan"
    _order = "changed_at desc"

    order_id = fields.Many2one("knr.order", required=True, ondelete="cascade")
    description = fields.Char(required=True)
    old_summary = fields.Text()
    new_summary = fields.Text()
    changed_by = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    changed_at = fields.Datetime(default=fields.Datetime.now, readonly=True)


class KnrProductionReport(models.Model):
    _name = "knr.production.report"
    _description = "Daftar Kebutuhan Produksi"

    service_date = fields.Date(default=fields.Date.context_today, required=True)
    department = fields.Selection([("bakery", "Bakery"), ("kitchen", "Dapur Saji")], required=True)
    order_ids = fields.Many2many("knr.order", compute="_compute_orders")
    line_ids = fields.Many2many("knr.order.line", compute="_compute_lines")

    @api.depends("service_date", "department")
    def _compute_orders(self):
        for rec in self:
            start = fields.Datetime.to_datetime(rec.service_date)
            end = fields.Datetime.add(start, days=1)
            rec.order_ids = self.env["knr.order"].search([("service_datetime", ">=", start), ("service_datetime", "<", end), ("state", "not in", ["cancel", "done"]), ("line_ids.department", "=", rec.department)])

    @api.depends("service_date", "department")
    def _compute_lines(self):
        for rec in self:
            start = fields.Datetime.to_datetime(rec.service_date)
            end = fields.Datetime.add(start, days=1)
            rec.line_ids = self.env["knr.order.line"].search([("order_id.service_datetime", ">=", start), ("order_id.service_datetime", "<", end), ("order_id.state", "not in", ["cancel", "done"]), ("department", "=", rec.department)])


class KnrDeliveryReport(models.Model):
    _name = "knr.delivery.report"
    _description = "Jadwal Pengiriman per Tanggal"

    service_date = fields.Date(default=fields.Date.context_today, required=True)
    order_ids = fields.Many2many("knr.order", compute="_compute_orders")

    @api.depends("service_date")
    def _compute_orders(self):
        for rec in self:
            start = fields.Datetime.to_datetime(rec.service_date)
            end = fields.Datetime.add(start, days=1)
            rec.order_ids = self.env["knr.order"].search([("service_datetime", ">=", start), ("service_datetime", "<", end), ("state", "not in", ["cancel", "done"])], order="service_datetime asc")
