from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Task, User, File
from datetime import datetime
import os
from werkzeug.utils import secure_filename

tasks = Blueprint('tasks', __name__, url_prefix='/tasks')

# ───────────────────────────────
# Create Task
# ───────────────────────────────
@tasks.route('/create', methods=['GET', 'POST'])
@login_required
def create_task():
    # Check if current user can assign tasks
    assignable_users = [user for user in User.query.all() if current_user.can_assign_task_to(user)]
    if not assignable_users:
        flash("❌ You do not have permission to assign tasks.", "danger")
        return redirect(url_for('tasks.task_dashboard'))

    files = File.query.all()

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        assigned_to_id = int(request.form.get("assigned_to"))
        due_date = request.form.get("due_date")
        selected_file_ids = request.form.getlist("file_ids")  # multiple files can be selected
        new_files = request.files.getlist("new_files")  # handle new file uploads

        # Validate assignment
        assigned_user = User.query.get(assigned_to_id)
        if not current_user.can_assign_task_to(assigned_user):
            flash("❌ You cannot assign a task to this user.", "danger")
            return redirect(url_for('tasks.create_task'))

        # Convert due_date
        try:
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d") if due_date else None
        except ValueError:
            flash("❌ Invalid date format. Use YYYY-MM-DD.", "danger")
            return redirect(url_for('tasks.create_task'))

        # Create the task
        new_task = Task(
            title=title,
            description=description,
            assigned_to_id=assigned_to_id,
            created_by_id=current_user.id,
            due_date=due_date_obj
        )

        # Handle existing file selections
        linked_files = []
        if selected_file_ids:
            selected_files = File.query.filter(File.id.in_(selected_file_ids)).all()
            linked_files.extend(selected_files)

        # Handle new file uploads
        UPLOAD_FOLDER = "uploads"
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        for new_file in new_files:
            if new_file and new_file.filename != "":
                filename = secure_filename(new_file.filename)
                path = os.path.join(UPLOAD_FOLDER, filename)
                new_file.save(path)

                file_record = File(
                    filename=filename,
                    original_filename=new_file.filename,
                    file_type=new_file.content_type,
                    user_id=current_user.id
                )
                db.session.add(file_record)
                db.session.commit()  # Commit to get the file ID
                linked_files.append(file_record)

        # Attach files to the task
        if linked_files:
            new_task.files = linked_files

        db.session.add(new_task)
        db.session.commit()
        flash("✅ Task created successfully.", "success")
        return redirect(url_for('tasks.task_dashboard'))

    return render_template("create_task.html", users=assignable_users, files=files)


# ───────────────────────────────
# Task Dashboard
# ───────────────────────────────
@tasks.route('/')
@login_required
def task_dashboard():
    if current_user.is_admin():
        tasks_list = Task.query.options(db.subqueryload(Task.files).subqueryload(File.uploader)).order_by(Task.created_at.desc()).all()
    else:
        tasks_list = Task.query.options(db.subqueryload(Task.files).subqueryload(File.uploader)).filter_by(assigned_to_id=current_user.id).order_by(Task.created_at.desc()).all()

    return render_template("task_dashboard.html", tasks=tasks_list)


# ───────────────────────────────
# View Task
# ───────────────────────────────
@tasks.route('/<int:task_id>')
@login_required
def view_task(task_id):
    task = Task.query.options(db.subqueryload(Task.files).subqueryload(File.uploader)).get_or_404(task_id)
    
    # Check if user has permission to view this task
    if not current_user.is_admin() and task.assigned_to_id != current_user.id:
        flash("❌ You do not have permission to view this task.", "danger")
        return redirect(url_for('tasks.task_dashboard'))
    
    return render_template("view_task.html", task=task)


# ───────────────────────────────
# Edit Task
# ───────────────────────────────
@tasks.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Check if user has permission to edit this task
    if not current_user.is_admin() and task.created_by_id != current_user.id:
        flash("❌ You do not have permission to edit this task.", "danger")
        return redirect(url_for('tasks.task_dashboard'))
    
    assignable_users = [user for user in User.query.all() if current_user.can_assign_task_to(user)]
    all_files = File.query.all()
    
    if request.method == "POST":
        task.title = request.form.get("title")
        task.description = request.form.get("description")
        task.assigned_to_id = int(request.form.get("assigned_to"))
        due_date = request.form.get("due_date")
        selected_file_ids = request.form.getlist("file_ids")
        
        # Validate assignment
        assigned_user = User.query.get(task.assigned_to_id)
        if not current_user.can_assign_task_to(assigned_user):
            flash("❌ You cannot assign a task to this user.", "danger")
            return redirect(url_for('tasks.edit_task', task_id=task.id))
        
        # Convert due_date
        try:
            task.due_date = datetime.strptime(due_date, "%Y-%m-%d") if due_date else None
        except ValueError:
            flash("❌ Invalid date format. Use YYYY-MM-DD.", "danger")
            return redirect(url_for('tasks.edit_task', task_id=task.id))
        
        # Update file associations
        linked_files = []
        if selected_file_ids:
            selected_files = File.query.filter(File.id.in_(selected_file_ids)).all()
            linked_files.extend(selected_files)
        
        task.files = linked_files
        db.session.commit()
        flash("✅ Task updated successfully.", "success")
        return redirect(url_for('tasks.view_task', task_id=task.id))
    
    return render_template("edit_task.html", task=task, users=assignable_users, files=all_files)


# ───────────────────────────────
# Delete Task
# ───────────────────────────────
@tasks.route('/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Check if user has permission to delete this task
    if not current_user.is_admin() and task.created_by_id != current_user.id:
        flash("❌ You do not have permission to delete this task.", "danger")
        return redirect(url_for('tasks.task_dashboard'))
    
    db.session.delete(task)
    db.session.commit()
    flash("✅ Task deleted successfully.", "success")
    return redirect(url_for('tasks.task_dashboard'))


# ───────────────────────────────
# Mark Task Complete
# ───────────────────────────────
@tasks.route('/<int:task_id>/complete', methods=['POST'])
@login_required
def mark_task_complete(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Check if user has permission to mark this task as complete
    if not current_user.is_admin() and task.assigned_to_id != current_user.id:
        flash("❌ You do not have permission to mark this task as complete.", "danger")
        return redirect(url_for('tasks.task_dashboard'))
    
    task.status = 'Completed'
    db.session.commit()
    flash("✅ Task marked as completed.", "success")
    return redirect(url_for('tasks.task_dashboard'))