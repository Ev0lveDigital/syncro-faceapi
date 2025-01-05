CREATE TABLE CameraConfiguration (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        camera_source TEXT NOT NULL,
        threshold REAL DEFAULT 0.6
    );

    CREATE TABLE Employee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        image TEXT,
        profile_picture TEXT,
        authorized INTEGER DEFAULT 0
    );

    CREATE TABLE Attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        date DATE NOT NULL,
        check_in_time DATETIME,
        check_out_time DATETIME,
        FOREIGN KEY (employee_id) REFERENCES Employee(id)
    );
