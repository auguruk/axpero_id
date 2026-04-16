from odoo import api, fields, models


class ResUsersCompanyEmail(models.Model):
    """Stores a per-user, per-company outgoing email address and HTML signature.

    One record exists for each (user, company) pair. Both fields are optional:
    leaving ``email`` empty falls back to the user's default partner email;
    leaving ``signature`` empty falls back to the user's default signature.
    """

    _name = 'res.users.company.email'
    _description = 'User Company Email Configuration'
    _rec_name = 'display_name'
    _order = 'user_id, company_id'

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        ondelete='cascade',
        index=True,
    )
    email = fields.Char(
        string='Email Address',
        help=(
            'Outgoing "From" address to use when this user sends email under '
            'this company. Leave blank to fall back to the user\'s default '
            'email address.'
        ),
    )
    signature = fields.Html(
        string='Email Signature',
        sanitize=False,
        help=(
            'HTML email signature to use when this user composes email under '
            'this company. Leave blank to fall back to the user\'s default '
            'signature.'
        ),
    )

    # Convenience computed fields used in tree/kanban views
    user_name = fields.Char(
        string='User Name',
        related='user_id.name',
        store=False,
        readonly=True,
    )
    company_name = fields.Char(
        string='Company Name',
        related='company_id.name',
        store=False,
        readonly=True,
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=False,
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    _sql_constraints = [
        (
            'user_company_unique',
            'unique(user_id, company_id)',
            'A user can only have one email configuration per company.',
        ),
    ]

    # -------------------------------------------------------------------------
    # Computed fields
    # -------------------------------------------------------------------------

    @api.depends('user_id', 'company_id')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.user_id:
                parts.append(rec.user_id.name)
            if rec.company_id:
                parts.append(rec.company_id.name)
            rec.display_name = ' – '.join(parts) if parts else ''

    # -------------------------------------------------------------------------
    # Onchange helpers
    # -------------------------------------------------------------------------

    @api.onchange('user_id')
    def _onchange_user_id(self):
        """Restrict company selection to companies the chosen user belongs to."""
        if self.user_id:
            allowed_company_ids = self.user_id.company_ids.ids
            return {
                'domain': {
                    'company_id': [('id', 'in', allowed_company_ids)],
                }
            }
        return {
            'domain': {
                'company_id': [],
            }
        }

    # -------------------------------------------------------------------------
    # Business logic helpers
    # -------------------------------------------------------------------------

    def get_email_formatted(self):
        """Return the formatted RFC-5322 "From" string, e.g. 'Alice <alice@example.com>'.

        Falls back gracefully to the user's default email if no company-specific
        address is configured.
        """
        self.ensure_one()
        from odoo.tools import formataddr

        name = self.user_id.name or ''
        address = self.email or self.user_id.email or ''
        if not address:
            return ''
        return formataddr((name, address))
