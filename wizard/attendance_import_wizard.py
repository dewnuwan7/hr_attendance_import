import base64
import io
import logging
from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

COLOMBO_TZ = pytz.timezone('Asia/Colombo')


def _parse_datetime(date_str, time_str):
    """
    Combine a date string (DD/MM/YYYY) and time string (HH:MM) into a
    UTC-aware datetime.  Returns None if either value is missing / '--'.
    """
    if not date_str or not time_str:
        return None
    date_str = str(date_str).strip()
    time_str = str(time_str).strip()
    if date_str == '--' or time_str == '--':
        return None
    try:
        local_dt = datetime.strptime(f'{date_str} {time_str}', '%d/%m/%Y %H:%M')
        local_dt = COLOMBO_TZ.localize(local_dt)
        return local_dt.astimezone(pytz.utc).replace(tzinfo=None)
    except ValueError:
        return None


class AttendanceImportWizard(models.TransientModel):
    _name = 'attendance.import.wizard'
    _description = 'Import Attendance Logs from Machine Excel'

    excel_file = fields.Binary(
        string='Machine Excel File',
        required=True,
        help='Upload the Excel file exported from the check-in/check-out machine.',
    )
    file_name = fields.Char(string='File Name')

    # ------------------------------------------------------------------ #
    #  Result fields (populated after import)                             #
    # ------------------------------------------------------------------ #
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done')],
        default='draft',
    )
    result_created = fields.Integer(string='Records Created', readonly=True)
    result_skipped = fields.Integer(string='Rows Skipped', readonly=True)
    result_errors = fields.Integer(string='Errors', readonly=True)
    result_details = fields.Text(string='Details', readonly=True)

    # ------------------------------------------------------------------ #
    #  Main import action                                                 #
    # ------------------------------------------------------------------ #
    def action_import(self):
        self.ensure_one()
        try:
            import openpyxl  # noqa: F401 – availability check
        except ImportError:
            raise UserError(
                _('The "openpyxl" Python library is required. '
                  'Install it with: pip install openpyxl')
            )

        if not self.excel_file:
            raise UserError(_('Please upload an Excel file before importing.'))

        raw = base64.b64decode(self.excel_file)
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
        except Exception as e:
            raise UserError(_('Could not read the Excel file: %s') % str(e))

        rows = list(ws.iter_rows(values_only=True))

        # ---- locate the header row ------------------------------------ #
        header_row_idx = None
        for idx, row in enumerate(rows):
            cells = [str(c).strip() if c is not None else '' for c in row]
            if 'Full Name' in cells and 'ID' in cells:
                header_row_idx = idx
                break

        if header_row_idx is None:
            raise UserError(
                _('Could not find the header row in the file. '
                  'Expected columns: Full Name, ID, Clock-In Date, '
                  'Clock-In Time, Clock-Out Date, Clock-Out Time.')
            )

        header = [str(c).strip() if c is not None else '' for c in rows[header_row_idx]]
        try:
            col_name = header.index('Full Name')
            col_id = header.index('ID')
            col_ci_date = header.index('Clock-In Date')
            col_ci_time = header.index('Clock-In Time')
            col_co_date = header.index('Clock-Out Date')
            col_co_time = header.index('Clock-Out Time')
        except ValueError as e:
            raise UserError(_('Missing expected column: %s') % str(e))

        data_rows = rows[header_row_idx + 1:]

        # ---- build Scan-ID → employee map ----------------------------- #
        employees = self.env['hr.employee'].search([
            ('attendance_scan_id', '!=', False),
            ('attendance_scan_id', '!=', ''),
        ])
        scan_map = {emp.attendance_scan_id.strip(): emp for emp in employees}

        created = 0
        skipped = 0
        errors = 0
        detail_lines = []

        for row_num, row in enumerate(data_rows, start=header_row_idx + 2):
            def cell(col):
                val = row[col] if col < len(row) else None
                return str(val).strip() if val is not None else '--'

            name_val = cell(col_name)
            id_val = cell(col_id)
            ci_date = cell(col_ci_date)
            ci_time = cell(col_ci_time)
            co_date = cell(col_co_date)
            co_time = cell(col_co_time)

            # Skip rows with no name
            if name_val == '--':
                skipped += 1
                continue

            # Skip rows where both check-in and check-out are absent
            ci_missing = ci_date == '--' or ci_time == '--'
            co_missing = co_date == '--' or co_time == '--'
            if ci_missing and co_missing:
                skipped += 1
                continue

            # Skip rows where only check-out exists (no check-in)
            if ci_missing and not co_missing:
                skipped += 1
                detail_lines.append(
                    _('Row %d (%s): skipped – check-out only, no check-in.') % (row_num, name_val)
                )
                continue

            # Match employee by Scan ID
            employee = scan_map.get(id_val)
            if not employee:
                errors += 1
                detail_lines.append(
                    _('Row %d (%s): no employee found with Scan ID "%s".') % (row_num, name_val, id_val)
                )
                continue

            check_in_utc = _parse_datetime(ci_date, ci_time)
            if check_in_utc is None:
                errors += 1
                detail_lines.append(
                    _('Row %d (%s): could not parse check-in datetime "%s %s".') % (
                        row_num, name_val, ci_date, ci_time)
                )
                continue

            check_out_utc = None if co_missing else _parse_datetime(co_date, co_time)

            # Validate check-out is after check-in when both present
            if check_out_utc and check_out_utc <= check_in_utc:
                errors += 1
                detail_lines.append(
                    _('Row %d (%s): check-out is not after check-in – skipped.') % (row_num, name_val)
                )
                continue

            # Check for duplicate (same employee + check_in already in DB)
            existing = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '=', check_in_utc),
            ], limit=1)
            if existing:
                skipped += 1
                detail_lines.append(
                    _('Row %d (%s): duplicate – record with same check-in already exists.') % (
                        row_num, name_val)
                )
                continue

            vals = {
                'employee_id': employee.id,
                'check_in': check_in_utc,
            }
            if check_out_utc:
                vals['check_out'] = check_out_utc

            try:
                self.env['hr.attendance'].create(vals)
                created += 1
            except Exception as e:
                errors += 1
                detail_lines.append(
                    _('Row %d (%s): failed to create record – %s') % (row_num, name_val, str(e))
                )

        summary = _(
            'Import complete.\n'
            '✔ Created : %d\n'
            '⏭ Skipped : %d\n'
            '✘ Errors  : %d\n'
        ) % (created, skipped, errors)

        if detail_lines:
            summary += '\n' + '\n'.join(detail_lines)

        self.write({
            'state': 'done',
            'result_created': created,
            'result_skipped': skipped,
            'result_errors': errors,
            'result_details': summary,
        })

        # Re-open the wizard to show results
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
