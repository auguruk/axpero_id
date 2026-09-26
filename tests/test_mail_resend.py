from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.mail.tests.common import MailCommon


@tagged('post_install', '-at_install')
class TestMailResend(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env['res.partner'].create({'name': 'Resend Customer', 'email': 'customer@example.com'})
        cls.attachment = cls.env['ir.attachment'].create({
            'name': 'invoice.txt', 'raw': b'invoice', 'res_model': 'res.partner', 'res_id': cls.customer.id,
        })

    def _sent_mail(self):
        mail = self.env['mail.mail'].with_user(self.user_admin).create({
            'subject': 'Your invoice',
            'body_html': '<p>Please find your invoice attached.</p>',
            'email_from': 'accounts@example.com',
            'email_to': 'other@example.com',
            'recipient_ids': [(4, self.customer.id)],
            'model': 'res.partner',
            'res_id': self.customer.id,
            'attachment_ids': [(4, self.attachment.id)],
            'auto_delete': False,
        })
        with self.mock_mail_gateway():
            mail.send()
        self.assertEqual(mail.state, 'sent')
        return mail

    def test_resend_sends_a_copy_with_a_new_message_id(self):
        mail = self._sent_mail()
        first_message_id = mail.message_id
        with self.mock_mail_gateway():
            action = mail.with_user(self.user_admin).action_resend()
        resent = self.env['mail.mail'].browse(action['res_id'])

        self.assertEqual(resent.state, 'sent')
        self.assertEqual(resent.resent_mail_id, mail)
        self.assertNotEqual(resent.mail_message_id, mail.mail_message_id)
        self.assertEqual((resent.subject, resent.body_html, resent.email_to, resent.recipient_ids),
                         (mail.subject, mail.body_html, mail.email_to, mail.recipient_ids))
        self.assertEqual(resent.attachment_ids, self.attachment)
        self.assertEqual((resent.model, resent.res_id), ('res.partner', self.customer.id))
        # the original is untouched: replies to the first email still reach the document
        self.assertEqual((mail.state, mail.message_id), ('sent', first_message_id))

        self.assertEqual(len(self._mails), 2)  # the customer and the email_to address
        for email in self._mails:
            self.assertNotEqual(email['message_id'], first_message_id)
            self.assertIn(first_message_id, email['references'])
            self.assertEqual(email['subject'], 'Your invoice')
        sent_to = ' '.join(address for email in self._mails for address in email['email_to'])
        self.assertIn('customer@example.com', sent_to)
        self.assertIn('other@example.com', sent_to)

    def test_only_sent_emails_can_be_resent(self):
        mail = self._sent_mail()
        mail.state = 'exception'
        with self.assertRaises(UserError):
            mail.with_user(self.user_admin).action_resend()
