from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import User
from extensions import db

# Define the blueprint (this keeps the import in app.py working as before)
auth = Blueprint('auth', __name__)


# ─────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get("email")  # Use email instead of username
        password = request.form.get("password")

        # Query only by email
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            session["role"] = user.role
            session["user_id"] = user.id
            flash(f"✅ Welcome {user.username}!")

            # Redirect based on role
            if user.is_admin():
                return redirect(url_for("admin.dashboard"))
            else:
                return redirect(url_for("main.home"))
        else:
            flash("❌ Invalid email or password.")  # Update message to reflect email

    return render_template("login.html")


# ─────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash("✅ You have been logged out.")
    return redirect(url_for("auth.login"))


# ─────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            flash("❌ Username or email already exists.")
            return redirect(url_for("auth.register"))

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method="pbkdf2:sha256"),
            role="user"  # default role is user
        )

        db.session.add(new_user)
        db.session.commit()

        flash("✅ Registration successful. Please log in.")
        return redirect(url_for("auth.login"))

    return render_template("register.html")
