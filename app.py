from flask import Flask
import os
from extensions import db, login_manager, socketio
from models import User

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secretkey'
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.root_path, 'app.db')}"
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    login_manager.login_view = 'auth.login'

    # Register blueprints
    from auth import auth as auth_bp
    from main import main as main_bp
    from files import files as files_bp
    from comments import comments as comments_bp
    from tasks import tasks as tasks_bp
    from admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(admin_bp)

    # Create database tables if not exist
    with app.app_context():
        db.create_all()

    return app

app = create_app()

if __name__ == '__main__':
    # Run SocketIO / Flask on localhost 127.0.0.1, port 5001
    socketio.run(app, debug=True, host='127.0.0.1', port=5001)
