import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import File, Comment, Task
from extensions import db
from utils import allowed_file

files = Blueprint('files', __name__)

# ─────────────────────────────────────────────────────────────
# Upload File
# ─────────────────────────────────────────────────────────────
@files.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('❌ No file part.')
        return redirect(url_for('main.dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('❌ No file selected.')
        return redirect(url_for('main.dashboard'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}_{filename}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(save_path)

        new_file = File(
            filename=unique_filename,
            original_filename=file.filename,
            file_type=filename.rsplit('.', 1)[1].lower(),
            user_id=current_user.id,
            upload_date=datetime.utcnow()
        )
        db.session.add(new_file)
        db.session.commit()
        flash('✅ File uploaded successfully.')
    else:
        flash('❌ Invalid file type.')
    return redirect(url_for('main.dashboard'))


# ─────────────────────────────────────────────────────────────
# View File Details + Comments
# ─────────────────────────────────────────────────────────────
@files.route('/view/<int:file_id>')
@login_required
def view_file(file_id):
    file = File.query.get_or_404(file_id)

    # Check if file is linked to any task
    linked_task = Task.query.filter(Task.files.any(id=file.id)).first()

    # Allow access if:
    if linked_task or file.user_id == current_user.id or current_user.role.lower() == 'admin':
        # Get comments attached to this file
        comments = file.comments  # <-- use relationship
        return render_template('view_file.html', file=file, comments=comments)
    else:
        flash("❌ You are not allowed to access this file.")
        return redirect(url_for("main.dashboard"))


# ─────────────────────────────────────────────────────────────
# Download File
# ─────────────────────────────────────────────────────────────
@files.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    file = File.query.get_or_404(file_id)

    # Check if file is linked to any task
    linked_task = Task.query.filter(Task.files.any(id=file.id)).first()

    # Allow download if linked to a task, uploader, or admin
    if not (linked_task or file.user_id == current_user.id or current_user.role == 'admin'):
        flash("❌ You are not allowed to download this file.")
        return redirect(url_for('main.dashboard'))

    # Send file for download
    return send_from_directory(
        directory=current_app.config['UPLOAD_FOLDER'],
        path=file.filename,
        as_attachment=True,
        download_name=file.original_filename
    )
