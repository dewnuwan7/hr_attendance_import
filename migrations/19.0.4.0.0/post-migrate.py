import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Create Check-In Override Settings action and menu on every upgrade."""
    from odoo import api, registry as Registry
    from odoo.modules.registry import Registry

    dbname = cr.dbname
    reg = Registry(dbname)
    with api.Environment.manage():
        env = api.Environment(cr, 1, {})  # uid=1 = admin

        IMD = env['ir.model.data']

        # ── Clean up old action ───────────────────────────────────────
        old = IMD.search([
            ('module', '=', 'hr_attendance_import'),
            ('name', '=', 'action_attendance_override_settings'),
        ], limit=1)
        if old:
            try:
                env[old.model].browse(old.res_id).unlink()
            except Exception:
                pass
            old.unlink()

        # ── Create action ─────────────────────────────────────────────
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

        # ── Clean up old menu ─────────────────────────────────────────
        old_m = IMD.search([
            ('module', '=', 'hr_attendance_import'),
            ('name', '=', 'menu_attendance_override_settings'),
        ], limit=1)
        if old_m:
            try:
                env[old_m.model].browse(old_m.res_id).unlink()
            except Exception:
                pass
            old_m.unlink()

        # ── Create menu ───────────────────────────────────────────────
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
        _logger.info('hr_attendance_import: Check-In Override Settings menu created.')
