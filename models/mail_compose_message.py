import re

from odoo import api, models
from odoo.tools import formataddr

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches the standard Odoo signature wrapper injected by the web client.
# Odoo 16+ wraps signatures in <div class="o_signature">…</div>.
_SIG_DIV_RE = re.compile(
    r'<div[^>]*\bclass=["\'][^"\']*\bo_signature\b[^"\']*["\'][^>]*>.*?</div>',
    re.DOTALL | re.IGNORECASE,
)

# Fallback: Odoo 15 and older used a <p>-- <br/> …</p> convention.
_SIG_P_RE = re.compile(
    r'<p>--\s*<br\s*/?>.*?</p>',
    re.DOTALL | re.IGNORECASE,
)


def _replace_signature(body: str, new_signature_html: str) -> str:
    """Replace the existing signature block in *body* with *new_signature_html*.

    Strategy (tried in order):
    1. Replace ``<div class="o_signature">…</div>`` (Odoo 16+).
    2. Replace ``<p>-- <br/>…</p>`` (Odoo ≤ 15 convention).
    3. Append the new signature at the end if no existing block is found.
    """
    replacement = f'<div class="o_signature">{new_signature_html}</div>'

    if _SIG_DIV_RE.search(body):
        return _SIG_DIV_RE.sub(replacement, body, count=1)

    if _SIG_P_RE.search(body):
        return _SIG_P_RE.sub(replacement, body, count=1)

    # No existing signature found – append.
    return body + replacement


class MailComposeMessage(models.TransientModel):
    """Extend the mail compose wizard to inject per-company email / signature.

    Two touch-points are overridden:

    ``default_get``
        Called when the compose wizard is first opened.  We inspect the
        current user + company and, if a configuration record exists:

        * Replace ``email_from`` with the company-specific address.
        * Replace (or append) the signature block inside ``body`` with the
          company-specific HTML signature.

    ``_compute_email_from`` (if present on the base model)
        Some Odoo versions recompute ``email_from`` via a stored compute
        after ``default_get`` runs.  We override it here so the company
        email is preserved even in that path.
    """

    _inherit = 'mail.compose.message'

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_current_user_company_config(self):
        """Return the ``res.users.company.email`` record for the current user
        and current company, or an empty recordset.
        """
        user = self.env.user
        if not user or user._is_public():
            return self.env['res.users.company.email']
        return user._get_company_email_config()

    # -------------------------------------------------------------------------
    # Override: default_get
    # -------------------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)

        config = self._get_current_user_company_config()
        if not config:
            return result

        user = self.env.user

        # --- email_from -------------------------------------------------------
        if 'email_from' in fields_list and config.email:
            result['email_from'] = formataddr((user.name or '', config.email))

        # --- body / signature -------------------------------------------------
        # Only inject when we have a company-specific signature AND the body
        # field was actually requested and returned something.
        if config.signature and 'body' in fields_list:
            body = result.get('body') or ''
            result['body'] = _replace_signature(body, config.signature)

        return result

    # -------------------------------------------------------------------------
    # Override: _compute_email_from (Odoo 17+ stored-compute path)
    # -------------------------------------------------------------------------

    def _compute_email_from(self):
        """After the standard computation, override with the company email
        for records that belong to the current user.

        This guard is defensive: if the base model does not define
        ``_compute_email_from`` as a compute method the ``super()`` call
        is still safe (it simply becomes a no-op via MRO).
        """
        super()._compute_email_from()

        user = self.env.user
        if not user or user._is_public():
            return

        config = user._get_company_email_config()
        if not config or not config.email:
            return

        formatted = formataddr((user.name or '', config.email))

        for record in self:
            # Only touch records authored by the current user so that
            # messages being sent on behalf of another user are unaffected.
            if record.author_id and record.author_id == user.partner_id:
                record.email_from = formatted

    # -------------------------------------------------------------------------
    # Override: get_record_data (Odoo ≤ 16 / discussion composer path)
    # -------------------------------------------------------------------------

    def get_record_data(self, values):
        """Older Odoo versions (≤ 16) expose ``get_record_data`` as the hook
        for populating composer defaults.  We extend it here for compatibility.
        """
        result = super().get_record_data(values)

        config = self._get_current_user_company_config()
        if not config:
            return result

        user = self.env.user

        if config.email and 'email_from' in result:
            result['email_from'] = formataddr((user.name or '', config.email))

        if config.signature and 'body' in result:
            body = result.get('body') or ''
            result['body'] = _replace_signature(body, config.signature)

        return result
