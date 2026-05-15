from odoo import _, fields, models
from odoo.exceptions import UserError


class AttendanceOverrideSettingsWizard(models.TransientModel):
    _name = 'hr.attendance.override.wizard'
    _description = 'Check-In Override Settings'

    override_enabled = fields.Boolean(
        string='Enable Check-In Override',
        help='When enabled, any check-in time earlier than the override time '
             'will be replaced with the override time during import.',
    )
    # Float time widget displays as HH:MM
    override_time = fields.Float(
        string='Override Check-In Time',
        help='Check-in times earlier than this (in Asia/Colombo) will be '
             'replaced with this time. E.g. 8.5 = 08:30.',
    )

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        res['override_enabled'] = company.attendance_override_enabled
        res['override_time']    = company.attendance_override_time
        return res

    def action_save(self):
        self.ensure_one()
        if self.override_enabled and not (0.0 <= self.override_time < 24.0):
            raise UserError(_('Override time must be between 00:00 and 23:59.'))
        self.env.company.sudo().write({
            'attendance_override_enabled': self.override_enabled,
            'attendance_override_time':    self.override_time,
        })
        return {'type': 'ir.actions.act_window_close'}

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
