from odoo import _, fields, models
from odoo.exceptions import UserError


class MailMail(models.Model):
    _inherit = 'mail.mail'

    resent_mail_id = fields.Many2one(
        'mail.mail', string='Resend Of', readonly=True, copy=False, index='btree_not_null', ondelete='set null',
        help='The sent email this one repeats.')

    def _prepare_resend_values(self):
        """Values of a new outgoing email repeating this sent one.

        The copy gets its own ``mail.message`` (dated now, with a new Message-Id): sharing the
        original's would send the same Message-Id twice, which mail providers drop as a duplicate,
        and sending overwrites the message's Message-Id, which would stop replies to the first
        email being routed to the document.
        """
        self.ensure_one()
        message = self.mail_message_id.copy({'date': fields.Datetime.now()})
        return {
            'mail_message_id': message.id,
            'resent_mail_id': self.id,
            'body_html': self.body_html,
            # thread the resend with the original in the recipients' mail clients
            'references': ' '.join(filter(None, [self.references, self.message_id])) or False,
            'email_to': self.email_to,
            'email_cc': self.email_cc,
            'recipient_ids': [(6, 0, self.recipient_ids.ids)],
            'state': 'outgoing',
            # the original keeps the record of the first send
            'auto_delete': False,
            'is_notification': False,
        }

    def action_resend(self):
        """Send a copy of each sent email now; the original stays as the record of the first send."""
        not_sent = self.filtered(lambda mail: mail.state != 'sent')
        if not_sent:
            raise UserError(_('Only sent emails can be resent: %s', ', '.join(not_sent.mapped('display_name'))))
        copies = self.env['mail.mail'].create([mail._prepare_resend_values() for mail in self])
        copies.send()
        if len(copies) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Email'),
                'res_model': 'mail.mail',
                'view_mode': 'form',
                'res_id': copies.id,
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Resent Emails'),
            'res_model': 'mail.mail',
            'view_mode': 'list,form',
            'domain': [('id', 'in', copies.ids)],
        }
