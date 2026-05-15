from . import models
from . import wizard


def post_init_hook(env):
    """Runs on fresh install — delegate to migration logic."""
    from odoo import api
    env2 = api.Environment(env.cr, 1, {})
    _create_override_menu(env2)


def _create_override_menu(env):
    IMD = env['ir.model.data']

    for name in ['action_attendance_override_settings', 'menu_attendance_override_settings']:
        old = IMD.search([('module', '=', 'hr_attendance_import'), ('name', '=', name)], limit=1)
        if old:
            try:
                env[old.model].browse(old.res_id).unlink()
            except Exception:
                pass
            old.unlink()

    action = env['ir.actions.act_window'].create({
        'name': 'Check-In Override Settings',
        'res_model': 'hr.attendance.override.wizard',
        'view_mode': 'form',
        'target': 'new',
    })
    IMD.create({
        'name': 'action_attendance_override_settings',
        'module': 'hr_attendance_import',
        'model': 'ir.actions.act_window',
        'res_id': action.id,
        'noupdate': False,
    })

    parent = env.ref('hr_attendance_import.menu_attendance_import_parent')
    group = env.ref('hr_attendance.group_hr_attendance_manager')
    menu = env['ir.ui.menu'].create({
        'name': 'Check-In Override Settings',
        'parent_id': parent.id,
        'action': 'ir.actions.act_window,%d' % action.id,
        'sequence': 2,
        'group_ids': [(4, group.id)],
    })
    IMD.create({
        'name': 'menu_attendance_override_settings',
        'module': 'hr_attendance_import',
        'model': 'ir.ui.menu',
        'res_id': menu.id,
        'noupdate': False,
    })
