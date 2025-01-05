from flask import Blueprint, render_template, Response, stream_with_context
    from ..utils import get_db_connection, detect_and_encode, encode_uploaded_images, recognize_faces
    import cv2
    import time
    from datetime import datetime
    from flask import current_app

    bp = Blueprint('core', __name__)

    def generate_frames(camera_source, threshold):
        cap = cv2.VideoCapture(camera_source)
        if not cap.isOpened():
            print("Error: Could not open video stream.")
            return

        last_recognition_time = {}  # Dictionary to store last recognition time for each person
        SUCCESS_DELAY = 2  # 2 seconds delay after successful operation
        success_time = None
        completed_attendance_detected = False

        def format_time(time):
            return time.strftime("%I:%M:%S %p")

        try:
            while True:
                success, frame = cap.read()
                if not success:
                    print("Error: Could not read frame.")
                    break

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                test_face_encodings = detect_and_encode(frame_rgb)

                if test_face_encodings:
                    known_face_encodings, known_face_names = encode_uploaded_images()
                    if known_face_encodings:
                        names = recognize_faces(np.array(known_face_encodings), known_face_names,
                                            test_face_encodings, threshold)

                        current_time = datetime.now()
                        for name in names:
                            if name != 'Not Recognized':
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("SELECT id FROM Employee WHERE name = ?", (name,))
                                employee = cursor.fetchone()

                                if employee:
                                    employee_id = employee[0]
                                    cursor.execute('''
                                        SELECT id, check_in_time, check_out_time
                                        FROM Attendance
                                        WHERE employee_id = ? AND date = DATE('now')
                                    ''', (employee_id,))
                                    attendance = cursor.fetchone()

                                    # Check if attendance is completed
                                    if attendance and attendance[1] and attendance[2]:
                                        if not completed_attendance_detected:
                                            completed_attendance_detected = True
                                            success_time = current_time
                                        continue

                                    # Check cooldown only for new actions
                                    perform_action = True
                                    if name in last_recognition_time:
                                        time_since_last = (current_time - last_recognition_time[name]).total_seconds()
                                        if time_since_last < 60:  # 60-second cooldown
                                            perform_action = False

                                    if not attendance:
                                        if perform_action:
                                            cursor.execute('''
                                                INSERT INTO Attendance (employee_id, date, check_in_time)
                                                VALUES (?, DATE('now'), ?)
                                            ''', (employee_id, current_time))
                                            conn.commit()
                                            last_recognition_time[name] = current_time
                                            success_time = current_time
                                            print(f"Check-in recorded for {name} at {format_time(current_time)}")

                                    elif not attendance[1]:  # check_in_time is NULL
                                        if perform_action:
                                            cursor.execute('''
                                                UPDATE Attendance
                                                SET check_in_time = ?
                                                WHERE id = ?
                                            ''', (current_time, attendance[0]))
                                            conn.commit()
                                            last_recognition_time[name] = current_time
                                            success_time = current_time
                                            print(f"Check-in recorded for {name} at {format_time(current_time)}")

                                    elif not attendance[2]:  # check_out_time is NULL
                                        time_since_checkin = (current_time - attendance[1]).total_seconds()
                                        if time_since_checkin >= 60 and perform_action:
                                            cursor.execute('''
                                                UPDATE Attendance
                                                SET check_out_time = ?
                                                WHERE id = ?
                                            ''', (current_time, attendance[0]))
                                            conn.commit()
                                            last_recognition_time[name] = current_time
                                            success_time = current_time
                                            print(f"Check-out recorded for {name} at {format_time(current_time)}")

                                conn.close()

                # Check if it's time to close
                if success_time is not None:
                    if (datetime.now() - success_time).total_seconds() >= SUCCESS_DELAY:
                        break

                if completed_attendance_detected:
                    if (datetime.now() - success_time).total_seconds() >= SUCCESS_DELAY:
                        break

                _, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                
                time.sleep(0.1)

        finally:
            cap.release()

    @bp.route('/video_feed')
    def video_feed():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT camera_source, threshold FROM CameraConfiguration LIMIT 1')
        camera_config = cursor.fetchone()
        conn.close()

        camera_source = 0  # Default to 0
        threshold = 0.6  # Default threshold

        if camera_config:
            camera_source = int(camera_config[0]) if camera_config[0].isdigit() else camera_config[0]
            threshold = camera_config[1]

        return Response(generate_frames(camera_source, threshold),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    @bp.route('/')
    def index():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.name, e.employee_id, a.date, a.check_in_time, a.check_out_time
            FROM Attendance a
            JOIN Employee e ON a.employee_id = e.id
            WHERE a.date = DATE('now')
            ORDER BY a.check_in_time DESC
            LIMIT 10
        ''')
        recent_attendance = cursor.fetchall()
        conn.close()

        return render_template('index.html', recent_attendance=recent_attendance)
