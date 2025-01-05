from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
    from ..utils import get_db_connection, format_datetime
    import os
    import io
    import csv
    from werkzeug.utils import secure_filename
    from datetime import datetime, timedelta
    import base64

    bp = Blueprint('admin', __name__)

    # Replace this with a proper authentication check
    def is_admin(user):
        # This is a placeholder. Implement actual admin authentication logic here.
        return True

    def admin_required(func):
        def wrapper(*args, **kwargs):
            if not is_admin(None):  # Replace None with actual user object if available
                flash('You must be an admin to access this page.', 'danger')
                return redirect(url_for('core.index'))
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper

    @bp.route('/register', methods=['GET', 'POST'])
    @admin_required
    def register_employee():
        if request.method == 'POST':
            employee_id = request.form['employee_id']
            name = request.form['name']
            image_data = request.form.get('image_data')
            profile_picture = request.files.get('profile_picture')

            conn = get_db_connection()
            cursor = conn.cursor()

            try:
                # Check if employee ID already exists
                cursor.execute("SELECT id FROM Employee WHERE employee_id = ?", (employee_id,))
                existing_employee = cursor.fetchone()
                if existing_employee:
                    flash('Employee ID already exists.', 'danger')
                    return render_template('admin/register_employee.html')

                # Handle profile picture upload
                profile_picture_path = None
                if profile_picture:
                    filename = secure_filename(profile_picture.filename)
                    profile_picture_path = os.path.join('employees', 'profile', filename)
                    profile_picture.save(os.path.join('app', 'static', 'uploads', profile_picture_path))

                # Handle captured image data
                image_path = None
                if image_data:
                    # Decode base64 image data and save it
                    header, encoded = image_data.split(",", 1)
                    image_file = base64.b64decode(encoded)
                    filename = secure_filename(f"{name}_capture.jpg")
                    image_path = os.path.join('employees', 'captured', filename)

                    with open(os.path.join('app', 'static', 'uploads', image_path), 'wb') as f:
                        f.write(image_file)

                cursor.execute('''
                    INSERT INTO Employee (employee_id, name, image, profile_picture, authorized)
                    VALUES (?, ?, ?, ?, ?)
                ''', (employee_id, name, image_path, profile_picture_path, 0))
                conn.commit()
                flash('Employee registered successfully!', 'success')
                return redirect(url_for('admin.register_employee'))
            except Exception as e:
                conn.rollback()
                flash(f'Error registering employee: {e}', 'danger')
            finally:
                conn.close()

        return render_template('admin/register_employee.html')

    @bp.route('/camera/config', methods=['GET', 'POST'])
    @admin_required
    def camera_config():
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'POST':
            name = request.form['name']
            camera_source = request.form['camera_source']
            threshold = request.form['threshold']

            try:
                cursor.execute('''
                    INSERT INTO CameraConfiguration (name, camera_source, threshold)
                    VALUES (?, ?, ?)
                ''', (name, camera_source, threshold))
                conn.commit()
                flash('Camera configuration created successfully!', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error creating camera configuration: {e}', 'danger')
            finally:
                conn.close()

            return redirect(url_for('admin.camera_config_list'))

        return render_template('admin/camera_config.html')

    @bp.route('/camera/list')
    @admin_required
    def camera_config_list():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM CameraConfiguration')
        configs = cursor.fetchall()
        conn.close()

        return render_template('admin/camera_config_list.html', configs=configs)

    @bp.route('/attendance', methods=['GET', 'POST'])
    @admin_required
    def attendance_report():
        conn = get_db_connection()
        cursor = conn.cursor()

        # Default: Get attendance for today
        from_date = request.args.get('from_date', datetime.now().strftime('%Y-%m-%d'))
        to_date = request.args.get('to_date', datetime.now().strftime('%Y-%m-%d'))
        employee_id = request.args.get('employee_id')

        query = '''
            SELECT e.name, e.employee_id, e.profile_picture, e.image, a.date, a.check_in_time, a.check_out_time
            FROM Attendance a
            JOIN Employee e ON a.employee_id = e.id
            WHERE a.date BETWEEN ? AND ?
        '''
        params = [from_date, to_date]

        if employee_id:
            query += " AND e.employee_id = ?"
            params.append(employee_id)

        query += " ORDER BY a.date, a.check_in_time"

        cursor.execute(query, params)
        attendance_data = cursor.fetchall()
        conn.close()

        # Fetch all employees for the filter dropdown
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM Employee")
        all_employees = cursor.fetchall()
        conn.close()

        if request.method == 'POST' and request.form.get('export') == 'csv':
            # Create a CSV in memory
            si = io.StringIO()
            cw = csv.writer(si)

            # Write header
            cw.writerow(['Employee ID', "Name", 'Date', 'Check-in Time', 'Check-out Time', 'Duration'])

            # Write data
            for record in attendance_data:
                duration = ""
                if record[5] and record[6]:
                    duration = (record[6] - record[5]).total_seconds()
                    duration = str(timedelta(seconds=int(duration)))
                cw.writerow([record[1], record[0], record[4], format_datetime(record[5]), format_datetime(record[6]), duration])

            # Prepare the file for download
            output = io.BytesIO()
            output.write(si.getvalue().encode('utf-8'))
            output.seek(0)
            si.close()

            return send_file(output, download_name='attendance_report.csv', as_attachment=True, mimetype='text/csv')

        return render_template('admin/attendance_report.html', attendance_data=attendance_data, all_employees=all_employees, from_date=from_date, to_date=to_date, selected_employee_id=employee_id, format_datetime=format_datetime)
