from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestCompanyEmailPreferences(TransactionCase):
    """Users manage their own company emails from Preferences, never anyone else's."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'email': 'info@example.com', 'alias_domain_id': False})
        cls.other_company = cls.env['res.company'].create({
            'name': 'Other Company', 'email': 'info@other.example.com', 'alias_domain_id': False})
        cls.foreign_company = cls.env['res.company'].create({
            'name': 'Foreign Company', 'email': 'info@foreign.example.com', 'alias_domain_id': False})
        cls.user = new_test_user(
            cls.env, login='prefs_user', groups='base.group_user',
            company_id=cls.company.id, company_ids=[Command.set([cls.company.id, cls.other_company.id])])
        cls.colleague = new_test_user(cls.env, login='prefs_colleague', groups='base.group_user')
        cls.colleague_config = cls.env['res.users.company.email'].create({
            'user_id': cls.colleague.id, 'company_id': cls.company.id, 'email': 'colleague@example.com'})

    def _own_write(self, commands, **vals):
        user = self.user.with_user(self.user)
        return user.write({'company_email_ids': commands, **vals})

    def test_user_manages_own_company_emails(self):
        self._own_write([Command.create({'company_id': self.other_company.id, 'email': 'me@other.example.com'})],
                        signature='<p>Me</p>')
        config = self.user.company_email_ids
        self.assertEqual((config.company_id, config.email), (self.other_company, 'me@other.example.com'))
        self.assertEqual(str(self.user.signature), '<p>Me</p>')

        self._own_write([Command.update(config.id, {'email': 'new@other.example.com'})])
        self.assertEqual(config.email, 'new@other.example.com')
        self.assertEqual(self.user.with_user(self.user).read(['company_email_ids'])[0]['company_email_ids'],
                         config.ids)

        self._own_write([Command.delete(config.id)])
        self.assertFalse(config.exists())

    def test_user_cannot_touch_a_colleagues_company_email(self):
        with self.assertRaises(AccessError):
            self._own_write([Command.update(self.colleague_config.id, {'email': 'hijack@example.com'})])
        with self.assertRaises(AccessError):
            self._own_write([Command.delete(self.colleague_config.id)])
        with self.assertRaises(AccessError):
            self._own_write([Command.link(self.colleague_config.id)])
        self.assertEqual((self.colleague_config.user_id, self.colleague_config.email),
                         (self.colleague, 'colleague@example.com'))

    def test_user_cannot_use_a_company_they_do_not_belong_to(self):
        with self.assertRaises(AccessError):
            self._own_write([Command.create({'company_id': self.foreign_company.id, 'email': 'x@example.com'})])

    def test_user_cannot_give_a_company_email_to_someone_else(self):
        self._own_write([Command.create({'company_id': self.company.id, 'user_id': self.colleague.id,
                                         'email': 'me@example.com'})])
        config = self.user.company_email_ids
        self.assertEqual(config.user_id, self.user)
        self._own_write([Command.update(config.id, {'user_id': self.colleague.id})])
        self.assertEqual(config.user_id, self.user)

    def test_address_must_use_a_domain_of_the_company(self):
        with self.assertRaises(ValidationError):
            self._own_write([Command.create({'company_id': self.other_company.id, 'email': 'me@example.com'})])
        with self.assertRaises(ValidationError):
            self._own_write([Command.create({'company_id': self.other_company.id, 'email': 'me@gmail.com'})])
        self._own_write([Command.create({'company_id': self.other_company.id, 'email': 'Me@Other.Example.com'})])
        config = self.user.company_email_ids
        with self.assertRaises(ValidationError):
            self._own_write([Command.update(config.id, {'email': 'me@foreign.example.com'})])
        # administrators are held to the same rule
        with self.assertRaises(ValidationError):
            self.colleague_config.email = 'colleague@gmail.com'

    def test_alias_domain_is_allowed(self):
        alias_domain = self.env['mail.alias.domain'].create({'name': 'mail.other.example.com'})
        self.other_company.alias_domain_id = alias_domain
        self._own_write([Command.create({'company_id': self.other_company.id, 'email': 'me@mail.other.example.com'})])
        self.assertEqual(self.user.company_email_ids.email, 'me@mail.other.example.com')

    def test_company_without_email_domain(self):
        no_domain_company = self.env['res.company'].create({'name': 'No Domain', 'alias_domain_id': False})
        self.user.company_ids = [Command.link(no_domain_company.id)]
        with self.assertRaises(ValidationError):
            self._own_write([Command.create({'company_id': no_domain_company.id, 'email': 'me@example.com'})])
        # a signature alone needs no address
        self._own_write([Command.create({'company_id': no_domain_company.id, 'signature': '<p>Me</p>'})])

    def test_preferences_form_shows_the_tab(self):
        view = self.env.ref('base.view_users_form_simple_modif')
        arch = self.env['res.users'].with_user(self.user).get_views([(view.id, 'form')])['views']['form']['arch']
        self.assertIn('company_email_ids', arch)
