# hr_attendance_import

**Attendance Import from Machine Logs**
Odoo 19 Community Edition — Custom Addon

---

## What it does

Allows HR managers to upload the Excel file exported from the
check-in/check-out time-card machine and automatically create
`hr.attendance` records in Odoo — no manual data entry needed.

---

## Installation

1. Copy the `hr_attendance_import` folder into your Odoo **addons path**
   (e.g. `/odoo/custom-addons/`).

2. Restart the Odoo server:
   ```
   sudo systemctl restart odoo
   ```

3. Enable **Developer Mode** in Odoo
   (Settings → General Settings → Developer Tools → Activate).

4. Go to **Apps**, click **Update Apps List**, search for
   `Attendance Import`, and install it.

5. Make sure `openpyxl` is installed in your Python environment:
   ```
   pip install openpyxl
   ```

---

## Setup — Employee Scan IDs

Before importing, each employee must have their **Scan ID** configured:

1. Go to **Employees** → open an employee record.
2. Click the **Settings** tab.
3. Under the **Attendance / Point of Sale** section, enter the
   machine-assigned ID (the value in the `ID` column of the Excel file)
   in the **Scan ID** field.
4. Save the record.

---

## Usage

1. Export the **Total Time Card** Excel from the attendance machine software.
2. Go to **Attendances → Management → Import Attendance Logs**.
3. Upload the Excel file and click **Import**.
4. A summary is shown: records created, rows skipped, and any errors.

---

## Import Rules

| Condition | Action |
|---|---|
| Both clock-in and clock-out are `--` | Silently skipped (employee absent) |
| Name is `--` | Silently skipped |
| Only clock-out present, no clock-in | Skipped (logged in details) |
| Only clock-in present, no clock-out | Imported with blank check-out |
| No employee found with matching Scan ID | Error logged in details |
| Duplicate record (same employee + check-in) | Skipped (logged in details) |
| Check-out is not after check-in | Error logged in details |

---

## Timezone

All datetimes are converted from **Asia/Colombo** to UTC before being
stored in Odoo, which is Odoo's standard behaviour.

---

## File Structure

```
hr_attendance_import/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── hr_employee.py          # Adds attendance_scan_id field
├── wizard/
│   ├── __init__.py
│   ├── attendance_import_wizard.py       # Core import logic
│   └── attendance_import_wizard_views.xml
├── views/
│   ├── hr_employee_views.xml   # Injects Scan ID into Settings tab
│   └── menu.xml                # Adds menu item under Management
└── security/
    └── ir.model.access.csv
```
