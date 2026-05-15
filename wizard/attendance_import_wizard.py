import base64
import io
import json
import logging
from datetime import datetime, timedelta

import pytz

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

COLOMBO_TZ = pytz.timezone('Asia/Colombo')


def _parse_datetime(date_str, time_str):
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


def _float_to_time_str(float_time):
    """Convert float hours (e.g. 8.5) to 'HH:MM' string."""
    hours   = int(float_time)
    minutes = int(round((float_time - hours) * 60))
    return f'{hours:02d}:{minutes:02d}'


def _apply_checkin_override(check_in_utc, override_float, date_str):
    """
    If the check-in (converted back to Colombo time) is earlier than
    override_float (e.g. 8.5 = 08:30), replace the time component with
    override_float on the same date and return the new UTC datetime.
    Returns the original check_in_utc unchanged if it is >= override_float.
    """
    # Convert UTC → Colombo to compare
    colombo_dt = check_in_utc.replace(tzinfo=pytz.utc).astimezone(COLOMBO_TZ)
    colombo_time_as_float = colombo_dt.hour + colombo_dt.minute / 60.0

    if colombo_time_as_float >= override_float:
        # On time or late — do not touch
        return check_in_utc

    # Build the override datetime in Colombo time on the same date
    override_hours   = int(override_float)
    override_minutes = int(round((override_float - override_hours) * 60))
    overridden_local = colombo_dt.replace(
        hour=override_hours,
        minute=override_minutes,
        second=0,
        microsecond=0,
    )
    return overridden_local.astimezone(pytz.utc).replace(tzinfo=None)


class AttendanceImportWizard(models.TransientModel):
    _name = 'attendance.import.wizard'
    _description = 'Import Attendance Logs from Machine Excel'

    excel_file = fields.Binary(
        string='Attendance Excel Report',
        required=True,
    )
    file_name = fields.Char(string='File Name')

    state = fields.Selection(
        [('draft', 'Draft'), ('preview', 'Preview'), ('done', 'Done')],
        default='draft',
    )

    # Preview summary counts
    preview_ready   = fields.Integer(string='Ready to Import', readonly=True)
    preview_skipped = fields.Integer(string='Will be Skipped', readonly=True)
    preview_errors  = fields.Integer(string='Errors / Warnings', readonly=True)
    preview_details = fields.Text(string='Preview Details', readonly=True)

    # Final result counts
    result_created = fields.Integer(string='Records Created', readonly=True)
    result_skipped = fields.Integer(string='Rows Skipped',    readonly=True)
    result_errors  = fields.Integer(string='Errors',          readonly=True)
    result_details = fields.Text(string='Details',            readonly=True)

    # Serialised pending records (JSON) — stored between preview and confirm
    pending_json = fields.Char(string='Pending JSON', readonly=True)

    def _reopen(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'hr_attendance_import.action_attendance_import_wizard'
        )
        action.update({
            'res_id':  self.id,
            'context': self.env.context,
        })
        return action

    def _parse_file(self):
        """
        Parse the Excel file. Returns (pending, skipped, errors, detail_lines).
        Applies the company-level Check-In Override if enabled.
        """
        try:
            import openpyxl
        except ImportError:
            raise UserError(_('The "openpyxl" Python library is required.'))

        raw = base64.b64decode(self.excel_file)
        try:
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            ws = wb.active
        except Exception as e:
            raise UserError(_('Could not read the Excel file: %s') % str(e))

        rows = list(ws.iter_rows(values_only=True))

        header_row_idx = None
        for idx, row in enumerate(rows):
            cells = [str(c).strip() if c is not None else '' for c in row]
            if 'Full Name' in cells and 'ID' in cells:
                header_row_idx = idx
                break

        if header_row_idx is None:
            raise UserError(_(
                'Could not find the header row. Expected columns: '
                'Full Name, ID, Clock-In Date, Clock-In Time, Clock-Out Date, Clock-Out Time.'
            ))

        header = [str(c).strip() if c is not None else '' for c in rows[header_row_idx]]
        try:
            col_name    = header.index('Full Name')
            col_id      = header.index('ID')
            col_ci_date = header.index('Clock-In Date')
            col_ci_time = header.index('Clock-In Time')
            col_co_date = header.index('Clock-Out Date')
            col_co_time = header.index('Clock-Out Time')
        except ValueError as e:
            raise UserError(_('Missing expected column: %s') % str(e))

        employees = self.env['hr.employee'].search([
            ('attendance_scan_id', '!=', False),
            ('attendance_scan_id', '!=', ''),
        ])
        scan_map = {emp.attendance_scan_id.strip(): emp for emp in employees}

        # ── Check-In Override settings ────────────────────────────────
        company          = self.env.company
        override_enabled = company.attendance_override_enabled
        override_float   = company.attendance_override_time  # e.g. 8.5

        pending      = []
        skipped      = 0
        errors       = 0
        detail_lines = []

        for row_num, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 2):
            def cell(col, r=row):
                val = r[col] if col < len(r) else None
                return str(val).strip() if val is not None else '--'

            name_val = cell(col_name)
            id_val   = cell(col_id)
            ci_date  = cell(col_ci_date)
            ci_time  = cell(col_ci_time)
            co_date  = cell(col_co_date)
            co_time  = cell(col_co_time)

            if name_val == '--':
                skipped += 1
                continue

            ci_missing = ci_date == '--' or ci_time == '--'
            co_missing = co_date == '--' or co_time == '--'

            if ci_missing and co_missing:
                skipped += 1
                continue

            if ci_missing and not co_missing:
                skipped += 1
                detail_lines.append(
                    f'Row {row_num} ({name_val}): skipped – check-out only, no check-in.'
                )
                continue

            employee = scan_map.get(id_val)
            if not employee:
                errors += 1
                detail_lines.append(
                    f'Row {row_num} ({name_val}): no employee with Scan ID "{id_val}".'
                )
                continue

            check_in_utc = _parse_datetime(ci_date, ci_time)
            if check_in_utc is None:
                errors += 1
                detail_lines.append(
                    f'Row {row_num} ({name_val}): invalid check-in datetime.'
                )
                continue

            # ── Apply Check-In Override if enabled ────────────────────
            if override_enabled and override_float:
                check_in_utc = _apply_checkin_override(
                    check_in_utc, override_float, ci_date
                )

            check_out_utc = None if co_missing else _parse_datetime(co_date, co_time)

            if check_out_utc and check_out_utc <= check_in_utc:
                errors += 1
                detail_lines.append(
                    f'Row {row_num} ({name_val}): check-out is not after check-in.'
                )
                continue

            existing = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in',    '=', check_in_utc),
            ], limit=1)
            if existing:
                skipped += 1
                detail_lines.append(
                    f'Row {row_num} ({name_val}): duplicate – already exists.'
                )
                continue

            pending.append({
                'employee_id':   employee.id,
                'employee_name': employee.name,
                'check_in':  check_in_utc.strftime('%Y-%m-%d %H:%M:%S'),
                'check_out': check_out_utc.strftime('%Y-%m-%d %H:%M:%S') if check_out_utc else '',
            })

        return pending, skipped, errors, detail_lines

    # ── Step 1: Preview ────────────────────────────────────────────────
    def action_preview(self):
        self.ensure_one()
        if not self.excel_file:
            raise UserError(_('Please upload a file first.'))

        pending, skipped, errors, detail_lines = self._parse_file()
        detail_text = '\n'.join(detail_lines) if detail_lines else ''

        self.write({
            'state':           'preview',
            'preview_ready':   len(pending),
            'preview_skipped': skipped,
            'preview_errors':  errors,
            'preview_details': detail_text,
            'pending_json':    json.dumps(pending),
        })
        return self._reopen()

    # ── Step 2: Confirm & Import ───────────────────────────────────────
    def action_confirm_import(self):
        self.ensure_one()
        pending = json.loads(self.pending_json or '[]')

        created        = 0
        runtime_errors = 0
        detail_lines   = []

        for rec in pending:
            try:
                vals = {
                    'employee_id': rec['employee_id'],
                    'check_in':    rec['check_in'],
                }
                if rec.get('check_out'):
                    vals['check_out'] = rec['check_out']
                self.env['hr.attendance'].create(vals)
                created += 1
            except Exception as e:
                runtime_errors += 1
                detail_lines.append(f"{rec['employee_name']}: failed – {str(e)}")

        total_skipped = self.preview_skipped
        total_errors  = self.preview_errors + runtime_errors

        summary = (
            f'Import complete.\n'
            f'✔ Created : {created}\n'
            f'⏭ Skipped : {total_skipped}\n'
            f'✘ Errors  : {total_errors}\n'
        )
        if detail_lines:
            summary += '\n' + '\n'.join(detail_lines)

        self.write({
            'state':          'done',
            'result_created': created,
            'result_skipped': total_skipped,
            'result_errors':  total_errors,
            'result_details': summary,
            'pending_json':   '',
        })
        return self._reopen()

    def action_back(self):
        self.write({'state': 'draft', 'pending_json': ''})
        return self._reopen()

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
