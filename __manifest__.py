{
    'name': 'Import Attendance Report',
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Import attendance data from time-card machine Excel exports',
    'description': """
        Allows HR managers to upload the Excel file exported from the
        check-in/check-out machine and automatically create attendance
        records in Odoo. Accessible via Attendances → Management →
        Import Attendance Logs.
    """,
    'author': 'Yushan Jayaweera',
    'depends': ['hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/attendance_import_wizard_views.xml',
        'views/hr_employee_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
