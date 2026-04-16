{
    'name': 'Axpero User Company Identity',
    'version': '19.0.1.0.0',
    'category': 'Discuss/Email',
    'summary': 'Per-company email address and signature for users',
    'description': """
User Company Email Signature
============================

Allows each user to configure a separate outgoing email address and email
signature for every company they belong to.

When a user composes an email while operating under Company A, Odoo will
automatically use the email address and signature configured for Company A.
Switching to Company B context uses Company B's address and signature instead.

Features
--------
* New model ``res.users.company.email`` stores one (email, HTML signature)
  record per user/company pair.
* User Preferences form gains a dedicated **Company Email Signatures** tab
  for self-service configuration.
* Administrators can manage settings for any user via the standard Users form.
* ``mail.compose.message`` is extended to inject the correct ``email_from``
  and signature into every new email draft automatically.
* Record rules ensure users can only read/write their own configurations;
  admins retain full access.
    """,
    'author': 'Axpero Services Ltd',
    'website': 'https://www.axpero.com',
    'depends': ['mail', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'security/res_users_company_email_rules.xml',
        #'views/res_users_company_email_views.xml',
        #'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
