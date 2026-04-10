import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import File, Comment, Task, User, TaskCategory
from models import File, Comment, Task, User, TaskCategory, Notification
from extensions import db

main = Blueprint('main', __name__)

# Upload folder for task file uploads
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Helper function to get users that current user can assign tasks to
def get_assignable_users(current_user):
    if current_user.is_admin():
        return User.query.order_by(User.username).all()
    else:
        all_users = User.query.order_by(User.username).all()
        return [user for user in all_users if current_user.can_assign_task_to(user)]

# Helper function to get tasks visible to current user based on role
def get_visible_tasks(current_user):
    if current_user.is_admin() or current_user.is_manager() or current_user.is_officer():
        # Admin, managers, and officers can see all tasks
        return Task.query
    else:
        # Supervisors and staff can only see tasks assigned to them or created by officers/supervisors
        officers_and_supervisors = User.query.filter(
            User.role.in_(['Department Officer', 'Department Supervisor'])
        ).all()
        officer_supervisor_ids = [user.id for user in officers_and_supervisors]
        
        return Task.query.filter(
            db.or_(
                Task.assigned_to_id == current_user.id,
                Task.created_by_id.in_(officer_supervisor_ids)
            )
        )

# ─────────────────────────────────────────────
# Landing Page / Login Redirect
# ─────────────────────────────────────────────
@main.route('/')
def index():
    # Redirect logged-in users to home
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    return render_template('login.html')


# ─────────────────────────────────────────────
# Home Page (Non-admin after login)
# ─────────────────────────────────────────────
@main.route('/home')
@login_required
def home():
    # Fetch all unread notifications for the logged-in user
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).all()

    return render_template('home.html', notifications=unread_notifications)

@main.route('/mark_notification_read/<int:id>', methods=['POST'])
@login_required
def mark_notification_read(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
    return '', 204


# ─────────────────────────────────────────────
# Task Dashboard (All tasks overview)
# ─────────────────────────────────────────────
@main.route('/dashboard')
@login_required
def dashboard():
    files = File.query.order_by(File.upload_date.desc()).all()
    general_comments = Comment.query.filter(~Comment.files.any()).order_by(Comment.timestamp.desc()).all()
    
    # Get tasks based on user role
    base_query = get_visible_tasks(current_user)
    tasks = base_query.options(
        db.subqueryload(Task.files).subqueryload(File.uploader)
    ).order_by(Task.due_date.asc()).all()

    return render_template(
        'task_dashboard.html',
        files=files,
        general_comments=general_comments,
        tasks=tasks,
        role=current_user.role
    )


# ─────────────────────────────────────────────
# View Tasks (with optional status filter)
# ─────────────────────────────────────────────
@main.route('/tasks')
@login_required
def view_tasks():
    status_filter = request.args.get('status')
    
    # Get tasks based on user role
    base_query = get_visible_tasks(current_user)
    query = base_query.options(
        db.subqueryload(Task.files).subqueryload(File.uploader)
    )
    if status_filter:
        query = query.filter_by(status=status_filter)
    tasks = query.order_by(Task.due_date.asc()).all()

    return render_template(
        'task_dashboard.html',
        tasks=tasks,
        filter=status_filter or 'all',
        role=current_user.role
    )


# ─────────────────────────────────────────────
# Create Task (with Categories, File Uploads & Notifications)
# ─────────────────────────────────────────────
@main.route('/create_task', methods=['GET', 'POST'])
@login_required
def create_task():
    # Get users that current user can assign to
    users = get_assignable_users(current_user)
    files = File.query.order_by(File.upload_date.desc()).all()
    categories = TaskCategory.query.order_by(TaskCategory.name).all()  # NEW

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        title = request.form.get('title')
        description = request.form.get('description')
        due_date_str = request.form.get('due_date')
        assigned_to_id = request.form.get('assigned_to')
        existing_file_ids = request.form.getlist('file_ids')
        new_files = request.files.getlist('new_files')

        # ─────── Validation ───────
        if not category_id or not title or not assigned_to_id:
            flash("❌ Category, title, and assignee are required.", "danger")
            return redirect(url_for('main.create_task'))

        # Convert due date string → date
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
        except ValueError:
            flash("❌ Invalid date format. Use YYYY-MM-DD.", "danger")
            return redirect(url_for('main.create_task'))

        # ─────── Handle File Uploads ───────
        linked_files = []

        # New uploads
        for new_file in new_files:
            if new_file and new_file.filename.strip() != "":
                filename = secure_filename(new_file.filename)
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                new_file.save(save_path)

                file_record = File(
                    filename=filename,
                    original_filename=new_file.filename,
                    file_type=new_file.content_type,
                    user_id=current_user.id,
                    upload_date=datetime.utcnow()
                )
                db.session.add(file_record)
                db.session.commit()  # Save before linking
                linked_files.append(file_record)

        # Existing file selections
        for fid in existing_file_ids:
            existing = File.query.get(fid)
            if existing:
                linked_files.append(existing)

        # ─────── Create New Task ───────
        new_task = Task(
            title=title,
            description=description,
            due_date=due_date,
            assigned_to_id=assigned_to_id,
            created_by_id=current_user.id,
            category_id=category_id,
            status='Pending',
            created_at=datetime.utcnow(),
            files=linked_files
        )

        db.session.add(new_task)
        db.session.commit()

        # ─────── Send Notification to Assignee ───────
        if assigned_to_id and int(assigned_to_id) != current_user.id:
            note = Notification(
                user_id=assigned_to_id,
                message=f"📋 New Task Assigned: {title}"
            )
            db.session.add(note)
            db.session.commit()

        flash("✅ Task created and assigned successfully!", "success")
        return redirect(url_for('main.dashboard'))

    return render_template(
        'create_task.html',
        users=users,
        files=files,
        categories=categories
    )


# ─────────────────────────────────────────────
# Admin: Manage Task Categories
# ─────────────────────────────────────────────
@main.route('/admin/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if not current_user.is_admin():
        flash("❌ Only admins can manage categories.")
        return redirect(url_for('main.dashboard'))

    categories = TaskCategory.query.order_by(TaskCategory.name).all()

    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form.get('name')

        if action == 'add' and name:
            existing = TaskCategory.query.filter_by(name=name).first()
            if existing:
                flash("❌ Category already exists.")
            else:
                new_cat = TaskCategory(name=name)
                db.session.add(new_cat)
                db.session.commit()
                flash("✅ Category added successfully.")
        elif action == 'delete':
            cat_id = request.form.get('category_id')
            cat = TaskCategory.query.get(cat_id)
            if cat:
                db.session.delete(cat)
                db.session.commit()
                flash("🗑️ Category deleted.")
        return redirect(url_for('main.manage_categories'))

    return render_template('manage_categories.html', categories=categories)


# ─────────────────────────────────────────────
# View/Download File
# ─────────────────────────────────────────────
@main.route('/view_file/<int:file_id>')
@login_required
def view_file(file_id):
    file = File.query.get_or_404(file_id)
    return send_from_directory(UPLOAD_FOLDER, file.filename, as_attachment=True)


# ─────────────────────────────────────────────
# Reassign Task (creator only)
# ─────────────────────────────────────────────
@main.route('/reassign_task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def reassign_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.created_by_id != current_user.id:
        flash("❌ You can only reassign tasks you created.")
        return redirect(url_for('main.dashboard'))

    # Get users that current user can assign to
    users = get_assignable_users(current_user)
    
    if request.method == "POST":
        task.assigned_to_id = int(request.form["assigned_to"])
        db.session.commit()
        flash("✅ Task reassigned successfully.")
        return redirect(url_for("main.dashboard"))

    return render_template("reassign_task.html", task=task, users=users)


@main.route('/tasks/<int:task_id>/accept', methods=['POST'])
@login_required
def accept_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Only the assigned user can accept
    if task.assigned_to_id != current_user.id:
        flash("You are not authorized to accept this task.", "danger")
        return redirect(url_for('main.view_tasks'))

    # Only accept if pending
    if task.status == "Pending":
        task.status = "Ongoing"
        db.session.commit()
        flash("Task accepted and now marked as Ongoing.", "success")
    else:
        flash("This task cannot be accepted.", "warning")

    return redirect(url_for('main.view_tasks'))


# ─────────────────────────────────────────────
# Mark Task Complete (creator only)
# ─────────────────────────────────────────────
@main.route('/mark_task_complete/<int:task_id>', methods=['POST'])
@login_required
def mark_task_complete(task_id):
    task = Task.query.get_or_404(task_id)
    if task.created_by_id != current_user.id:
        flash("❌ Only the creator can mark this task as completed.")
        return redirect(url_for('main.dashboard'))

    task.status = 'Completed'
    db.session.commit()
    flash("✅ Task marked as completed.")
    return redirect(url_for('main.dashboard'))


# ─────────────────────────────────────────────
# Delete Task (creator only)
# ─────────────────────────────────────────────
@main.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.created_by_id != current_user.id:
        flash("❌ Only the creator can delete this task.")
        return redirect(url_for('main.dashboard'))

    db.session.delete(task)
    db.session.commit()
    flash("🗑️ Task deleted successfully.")
    return redirect(url_for('main.dashboard'))


# ─────────────────────────────────────────────
# Reports / Statistics (Departmental Overview with Date Filters)
# ─────────────────────────────────────────────
@main.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    from sqlalchemy import extract, func
    from datetime import datetime

    # ───────────────
    # Handle date range input
    # ───────────────
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = Task.query
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Task.created_at >= start_dt)
        except ValueError:
            flash("⚠️ Invalid start date format (use YYYY-MM-DD).", "warning")
            start_dt = None
    else:
        start_dt = None

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.filter(Task.created_at <= end_dt)
        except ValueError:
            flash("⚠️ Invalid end date format (use YYYY-MM-DD).", "warning")
            end_dt = None
    else:
        end_dt = None

    # ───────────────
    # Summary Counts
    # ───────────────
    completed_count = query.filter_by(status="Completed").count()
    ongoing_count = query.filter_by(status="Ongoing").count()
    pending_count = query.filter_by(status="Pending").count()
    total_count = query.count()

    # ───────────────
    # Monthly Breakdown (Status trends)
    # ───────────────
    monthly_query = (
        db.session.query(
            extract('year', Task.created_at).label('year'),
            extract('month', Task.created_at).label('month'),
            Task.status,
            func.count(Task.id)
        )
        .filter(Task.id.in_([t.id for t in query]))  # filter by same criteria
        .group_by('year', 'month', Task.status)
        .order_by('year', 'month')
        .all()
    )

    month_map = {}
    for year, month, status, count in monthly_query:
        label = f"{int(year)}-{int(month):02d}"
        if label not in month_map:
            month_map[label] = {"Completed": 0, "Ongoing": 0, "Pending": 0}
        month_map[label][status] = count

    labels = sorted(month_map.keys())
    completed = [month_map[l]["Completed"] for l in labels]
    ongoing = [month_map[l]["Ongoing"] for l in labels]
    pending = [month_map[l]["Pending"] for l in labels]

    monthly_data = {
        "labels": labels,
        "completed": completed,
        "ongoing": ongoing,
        "pending": pending,
    }

    # ───────────────
    # Cumulative Tasks Trend
    # ───────────────
    cumulative_values = []
    running_total = 0
    for i, label in enumerate(labels):
        running_total += completed[i] + ongoing[i] + pending[i]
        cumulative_values.append(running_total)

    cumulative_data = {"labels": labels, "values": cumulative_values}

    # ───────────────
    # Task Categories Breakdown
    # ───────────────
    category_query = (
        db.session.query(TaskCategory.name, func.count(Task.id))
        .join(Task, Task.category_id == TaskCategory.id)
        .filter(Task.id.in_([t.id for t in query]))
        .group_by(TaskCategory.name)
        .order_by(TaskCategory.name)
        .all()
    )

    if not category_query:
        category_data = []
    else:
        total_tasks = sum(count for _, count in category_query) or 1
        category_data = [
            {
                "category": name or "Uncategorized",
                "count": count,
                "percentage": (count / total_tasks) * 100,
            }
            for name, count in category_query
        ]

    category_chart_data = {
        "labels": [c["category"] for c in category_data],
        "counts": [c["count"] for c in category_data],
    }

    # ───────────────
    # Task Assignment Load (per user)
    # ───────────────
    user_task_stats = (
        db.session.query(User.username, func.count(Task.id))
        .join(Task, Task.assigned_to_id == User.id)
        .filter(Task.id.in_([t.id for t in query]))
        .group_by(User.username)
        .all()
    )
    user_labels = [u[0] for u in user_task_stats]
    user_counts = [u[1] for u in user_task_stats]

    user_data = {
        "labels": user_labels,
        "counts": user_counts,
    }

    # ───────────────
    # Render Template
    # ───────────────
    return render_template(
        "reports.html",
        completed_count=completed_count,
        ongoing_count=ongoing_count,
        pending_count=pending_count,
        total_count=total_count,
        monthly_data=monthly_data,
        cumulative_data=cumulative_data,
        category_data=category_data,
        category_chart_data=category_chart_data,
        user_data=user_data,
        start_date=start_date,
        end_date=end_date
    )

# ─────────────────────────────────────────────
# Export Department Reports (PDF or Excel)
# ─────────────────────────────────────────────
@main.route('/export_report')
@login_required
def export_report():
    import io
    import pandas as pd
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from flask import send_file

    format = request.args.get('format', 'pdf')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Base query
    query = Task.query
    if start_date:
        query = query.filter(Task.created_at >= start_date)
    if end_date:
        query = query.filter(Task.created_at <= end_date)

    tasks = query.all()

    # Prepare data for export
    data = [
        ["Task Title", "Assigned To", "Status", "Category", "Created At", "Due Date"]
    ]
    for t in tasks:
        data.append([
            t.title,
            t.assigned_to.username if t.assigned_to else "Unassigned",
            t.status,
            t.category.name if t.category else "N/A",
            t.created_at.strftime("%Y-%m-%d"),
            t.due_date.strftime("%Y-%m-%d") if t.due_date else "—"
        ])

    # ───────────────
    # Export to Excel
    # ───────────────
    if format == "excel":
        df = pd.DataFrame(data[1:], columns=data[0])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Department Report")
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"department_report.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # ───────────────
    # Export to PDF
    # ───────────────
    elif format == "pdf":
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Header
        elements.append(Paragraph("Department Task Report", styles["Title"]))
        if start_date or end_date:
            elements.append(Paragraph(f"Period: {start_date or '—'} to {end_date or '—'}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Table
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"department_report.pdf",
            mimetype="application/pdf"
        )

    # ───────────────
    # Fallback
    # ───────────────
    flash("Unsupported export format.", "danger")
    return redirect(url_for("main.reports"))


# ─────────────────────────────────────────────
# Task Comments with File Attachments & Notifications
# ─────────────────────────────────────────────
@main.route('/task/<int:task_id>/comments', methods=['GET', 'POST'])
@login_required
def task_comments(task_id):
    task = Task.query.get_or_404(task_id)

    # ─────── Authorization Control ───────
    user = current_user
    if not user.is_admin() and not user.is_manager() and not user.is_officer():
        # Supervisors & Staff: Can only view tasks they are assigned to
        # or created by a Department Officer/Supervisor
        allowed_creators = User.query.filter(
            User.role.in_(['Department Officer', 'Department Supervisor'])
        ).with_entities(User.id).all()
        allowed_creator_ids = [u.id for u in allowed_creators]

        if task.assigned_to_id != user.id and task.created_by_id not in allowed_creator_ids:
            flash("🚫 You are not authorized to view this task.", "danger")
            return redirect(url_for('main.dashboard'))

    # ─────── Handle Comment Submission ───────
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        new_files = request.files.getlist('comment_files')

        if not content and not any(f.filename for f in new_files):
            flash("⚠️ Comment cannot be empty.", "warning")
            return redirect(url_for('main.task_comments', task_id=task.id))

        # Create and store comment
        comment = Comment(
            content=content,
            task_id=task.id,
            user_id=user.id,
            timestamp=datetime.utcnow()
        )
        db.session.add(comment)
        db.session.flush()  # So we can attach files before committing

        # ─────── Handle File Uploads ───────
        for uploaded_file in new_files:
            if uploaded_file and uploaded_file.filename.strip() != "":
                original_name = secure_filename(uploaded_file.filename)
                timestamped_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{original_name}"
                filepath = os.path.join(UPLOAD_FOLDER, timestamped_name)
                uploaded_file.save(filepath)

                file_record = File(
                    filename=timestamped_name,
                    original_filename=original_name,
                    file_type=uploaded_file.content_type,
                    user_id=user.id,
                    upload_date=datetime.utcnow()
                )
                db.session.add(file_record)
                db.session.flush()

                # Link file to comment
                comment.files.append(file_record)

        db.session.commit()

        # ─────── Notifications ───────
        notified_users = set()

        # Notify the task creator (if not the commenter)
        if task.created_by_id and task.created_by_id != user.id:
            creator_note = Notification(
                user_id=task.created_by_id,
                message=f"💬 New comment on your task: {task.title}"
            )
            db.session.add(creator_note)
            notified_users.add(task.created_by_id)

        # Notify the task assignee (if different from commenter & creator)
        if task.assigned_to_id and task.assigned_to_id not in notified_users and task.assigned_to_id != user.id:
            assignee_note = Notification(
                user_id=task.assigned_to_id,
                message=f"💬 New comment on your assigned task: {task.title}"
            )
            db.session.add(assignee_note)

        db.session.commit()

        flash("✅ Comment added successfully.", "success")
        return redirect(url_for('main.task_comments', task_id=task.id))

    # ─────── Load Comments & Files ───────
    comments = Comment.query.filter_by(task_id=task.id).order_by(Comment.timestamp.asc()).all()
    return render_template('task_comments.html', task=task, comments=comments)
