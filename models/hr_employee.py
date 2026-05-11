from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    attendance_scan_id = fields.Char(
        string='Scan ID',
        help='ID assigned by the attendance/check-in machine. '
             'Must match the ID column in the exported Excel file.',
        groups='hr.group_hr_user',
    )
