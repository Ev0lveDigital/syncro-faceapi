from flask import Flask
    from .routes import core, admin
    from .utils import initialize_db
    import os

    def create_app():
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a strong secret key
        app.config['DATABASE'] = os.path.join(app.root_path, 'attendance.db')
        app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

        initialize_db(app)

        app.register_blueprint(core.bp)
        app.register_blueprint(admin.bp, url_prefix='/admin')

        return app
