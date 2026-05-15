def migrate(cr, version):
    """Add override columns to res_company if they don't exist yet."""
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS attendance_override_enabled boolean DEFAULT false;
    """)
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS attendance_override_time double precision DEFAULT 8.5;
    """)
    # Force action name update so dialog title is correct
    cr.execute("""
        UPDATE ir_act_window
        SET name = 'Check-In Override Settings'
        WHERE res_model = 'hr.attendance.override.wizard'
    """)
