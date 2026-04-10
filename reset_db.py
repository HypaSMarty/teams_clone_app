from extensions import db
from app import create_app
from models import User
from datetime import datetime

app = create_app()

with app.app_context():
    # Drop all existing tables
    db.drop_all()

    # Create tables based on current models
    db.create_all()

    # Create default admin user
    admin = User(username="admin", email="admin@example.com", role="Admin")
    admin.set_password("admin123")  # Change this password if you want
    db.session.add(admin)
    db.session.commit()

    print("✅ Database reset and admin user created successfully.")
