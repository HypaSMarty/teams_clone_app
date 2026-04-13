from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import User, Task
from extensions import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ───────────────────────────────
# Admin Dashboard
# ───────────────────────────────
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin():
        flash("❌ Access denied.", "danger")
        return redirect(url_for("main.home"))

    total_users = User.query.count()
    total_tasks = Task.query.count()
    return render_template("admin_dashboard.html", total_users=total_users, total_tasks=total_tasks)


# ───────────────────────────────
# Manage Users
# ───────────────────────────────
@admin_bp.route('/manage_users')
@login_required
def manage_users():
    if not current_user.is_admin():
        flash("❌ Access denied.", "danger")
        return redirect(url_for("main.home"))

    users = User.query.order_by(User.username).all()
    roles = ["Admin", "Department Manager", "Department Officer", "Department Supervisor", "Administrative Assistant"]
    return render_template("manage_users.html", users=users, roles=roles)


# ───────────────────────────────
# Update User Role (Promote / Demote)
# ───────────────────────────────
@admin_bp.route('/update_role/<int:user_id>', methods=['POST'])
@login_required
def update_role(user_id):
    if not current_user.is_admin():
        flash("❌ Access denied.", "danger")
        return redirect(url_for("main.home"))

    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    valid_roles = ["Admin", "Department Manager", "Department Officer", "Department Supervisor", "Administrative Assistant"]

    if new_role not in valid_roles:
        flash("❌ Invalid role selected.", "danger")
        return redirect(url_for('admin.manage_users'))

    user.role = new_role
    db.session.commit()
    flash(f"✅ Updated {user.username}'s role to {new_role}.", "success")
    return redirect(url_for('admin.manage_users'))


# ───────────────────────────────
# Delete User
# ───────────────────────────────
@admin_bp.route('/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if not current_user.is_admin():
        flash("❌ Access denied.", "danger")
        return redirect(url_for("main.home"))

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("❌ You cannot delete your own account.", "warning")
        return redirect(url_for("admin.manage_users"))

    db.session.delete(user)
    db.session.commit()
    flash(f"🗑️ User {user.username} has been deleted.", "success")
    return redirect(url_for("admin.manage_users"))


# ───────────────────────────────
# Reset User Password
# ───────────────────────────────
@admin_bp.route('/reset_password/<int:user_id>', methods=['GET', 'POST'])
@login_required
def reset_user_password(user_id):
    if not current_user.is_admin():
        flash("❌ Access denied.", "danger")
        return redirect(url_for("main.home"))

    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not new_password or new_password != confirm_password:
            flash("❌ Passwords do not match or empty.", "danger")
            return redirect(url_for("admin.reset_user_password", user_id=user.id))

        user.set_password(new_password)
        db.session.commit()
        flash(f"✅ Password for {user.username} has been reset.", "success")
        return redirect(url_for("admin.manage_users"))

    return render_template("admin_reset_password.html", user=user)


# ───────────────────────────────
# Manage Tasks (Admin Only)
# ───────────────────────────────
@admin_bp.route('/manage_tasks')
@login_required
def manage_tasks():
    if not current_user.is_admin():
        flash("❌ Access denied.", "danger")
        return redirect(url_for("main.home"))

    tasks = Task.query.order_by(Task.created_at.desc()).all()
    return render_template("manage_tasks.html", tasks=tasks)
