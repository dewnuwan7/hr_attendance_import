{
    'name': 'Import Attendance Report',
    'version': '19.0.4.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Import attendance data from time-card machine Excel exports',
    'author': 'Yushan Jayaweera',
    'depends': ['hr_attendance'],
    'data': [
        'wizard/attendance_import_wizard_views.xml',
        'views/hr_employee_views.xml',
        'views/attendance_override_settings_views.xml',
        'views/menu.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
