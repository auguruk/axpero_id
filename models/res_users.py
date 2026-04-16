from odoo import api, fields, models
from odoo.tools import formataddr


class ResUsers(models.Model):
    """Extends res.users with per-company email/signature helpers."""

    _inherit = 'res.users'

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    company_email_ids = fields.One2many(
        comodel_name='res.users.company.email',
        inverse_name='user_id',
        string='Company Email Configurations',
        help=(
            'One record per company the user belongs to. '
            'Each record can override the outgoing email address and '
            'HTML signature for that specific company context.'
        ),
    )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def _get_company_email_config(self, company_id=None):
        """Return the ``res.users.company.email`` record for this user and the
        given (or current environment) company, or an empty recordset if none
        exists.

        :param company_id: (int) ID of the company to look up. Defaults to
                           ``self.env.company.id`` when omitted.
        :rtype: res.users.company.email recordset (may be empty)
        """
        self.ensure_one()
        if company_id is None:
            company_id = self.env.company.id
        return (
            self.env['res.users.company.email']
            .sudo()
            .search(
                [('user_id', '=', self.id), ('company_id', '=', company_id)],
                limit=1,
            )
        )

    def get_company_email(self, company_id=None):
        """Return the outgoing email address for this user under the given
        company, falling back to the user's default email if not set.

        :param company_id: (int) company ID; defaults to current company.
        :rtype: str
        """
        self.ensure_one()
        config = self._get_company_email_config(company_id)
        if config and config.email:
            return config.email
        return self.email or ''

    def get_company_email_formatted(self, company_id=None):
        """Return RFC-5322 formatted "From" string for this user under the
        given company, e.g. ``'Alice <alice@example.com>'``.

        :param company_id: (int) company ID; defaults to current company.
        :rtype: str
        """
        self.ensure_one()
        email = self.get_company_email(company_id)
        if not email:
            return ''
        return formataddr((self.name or '', email))

    def get_company_signature(self, company_id=None):
        """Return the HTML email signature for this user under the given
        company, falling back to the user's default signature if not set.

        :param company_id: (int) company ID; defaults to current company.
        :rtype: str or False
        """
        self.ensure_one()
        config = self._get_company_email_config(company_id)
        if config and config.signature:
            return config.signature
        return self.signature or ''

    # -------------------------------------------------------------------------
    # Override: make IMAP / Discuss aware of the per-company email
    # -------------------------------------------------------------------------

    @api.model
    def _get_default_signature(self):
        """Extend the default signature lookup to prefer the company-specific
        signature when one is configured for the current user + company pair.

        Called by ``mail.compose.message`` and other composers in Odoo 17+.
        """
        user = self.env.user
        if user and not user._is_public():
            config = user._get_company_email_config()
            if config and config.signature:
                return config.signature
        return super()._get_default_signature() if hasattr(super(), '_get_default_signature') else self.env.user.signature
