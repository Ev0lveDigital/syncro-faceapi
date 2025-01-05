import sqlite3
    from flask import current_app, g
    from datetime import timedelta
    import cv2
    import numpy as np
    import torch
    from facenet_pytorch import InceptionResnetV1, MTCNN

    # Initialize MTCNN and InceptionResnetV1
    mtcnn = MTCNN(keep_all=True)
    resnet = InceptionResnetV1(pretrained='vggface2').eval()

    def get_db_connection():
        if 'db' not in g:
            g.db = sqlite3.connect(
                current_app.config['DATABASE'],
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row
        return g.db

    def close_db_connection(error=None):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    def initialize_db(app):
        db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        cursor = db.cursor()

        # Create CameraConfiguration table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS CameraConfiguration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                camera_source TEXT NOT NULL,
                threshold REAL DEFAULT 0.6
            )
        ''')

        # Create Employee table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Employee (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                image TEXT,
                profile_picture TEXT,
                authorized INTEGER DEFAULT 0
            )
        ''')

        # Create Attendance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                date DATE NOT NULL,
                check_in_time DATETIME,
                check_out_time DATETIME,
                FOREIGN KEY (employee_id) REFERENCES Employee(id)
            )
        ''')

        db.commit()
        db.close()

        app.teardown_appcontext(close_db_connection)

    def format_datetime(dt):
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return ""

    def seconds_to_time(seconds):
        return str(timedelta(seconds=seconds))

    def detect_and_encode(image):
        with torch.no_grad():
            boxes, _ = mtcnn.detect(image)
            if boxes is not None:
                faces = []
                for box in boxes:
                    face = image[int(box[1]):int(box[3]), int(box[0]):int(box[2])]
                    if face.size == 0:
                        continue
                    face = cv2.resize(face, (160, 160))
                    face = np.transpose(face, (2, 0, 1)).astype(np.float32) / 255.0
                    face_tensor = torch.tensor(face).unsqueeze(0)
                    encoding = resnet(face_tensor).detach().numpy().flatten()
                    faces.append(encoding)
                return faces
        return []

    def encode_uploaded_images():
        known_face_encodings = []
        known_face_names = []

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch only authorized images
        cursor.execute("SELECT name, image FROM Employee WHERE authorized = 1")
        uploaded_images = cursor.fetchall()
        conn.close()

        for employee in uploaded_images:
            if employee[1]:  # Check if image path exists
                image_path = os.path.join(current_app.root_path, 'static', 'uploads', employee[1])
                if os.path.exists(image_path):
                    known_image = cv2.imread(image_path)
                    known_image_rgb = cv2.cvtColor(known_image, cv2.COLOR_BGR2RGB)
                    encodings = detect_and_encode(known_image_rgb)
                    if encodings:
                        known_face_encodings.extend(encodings)
                        known_face_names.append(employee[0])

        return known_face_encodings, known_face_names

    def recognize_faces(known_encodings, known_names, test_encodings, threshold=0.6):
        recognized_names = []
        for test_encoding in test_encodings:
            distances = np.linalg.norm(known_encodings - test_encoding, axis=1)
            min_distance_idx = np.argmin(distances)
            if distances[min_distance_idx] < threshold:
                recognized_names.append(known_names[min_distance_idx])
            else:
                recognized_names.append('Not Recognized')
        return recognized_names
