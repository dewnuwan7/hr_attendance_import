from odoo import fields, models


class ResCompany(models.Model):
    """Stores the Check-In Override settings persistently on the company."""
    _inherit = 'res.company'

    attendance_override_enabled = fields.Boolean(
        string='Enable Check-In Override',
        default=False,
    )
    # Stored as float: hours since midnight. E.g. 08:30 = 8.5
    attendance_override_time = fields.Float(
        string='Override Check-In Time',
        default=8.5,
        help='Check-in times earlier than this will be replaced with this time during import. '
             'Stored as decimal hours (e.g. 8.5 = 08:30).',
    )
