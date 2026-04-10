from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Comment
from extensions import db
from datetime import datetime

comments = Blueprint('comments', __name__)

@comments.route('/add_comment/<int:file_id>', methods=['POST'])
@login_required
def add_comment(file_id):
    content = request.form.get('comment')  # updated to match form field name
    if not content:
        flash('Comment cannot be empty.')
        return redirect(url_for('main.dashboard'))

    comment = Comment(
        content=content,
        user_id=current_user.id,
        file_id=file_id,
        timestamp=datetime.utcnow()
    )
    db.session.add(comment)
    db.session.commit()
    flash('✅ Comment added.')
    return redirect(url_for('main.dashboard'))

@comments.route('/add_general_comment', methods=['POST'])
@login_required
def add_general_comment():
    content = request.form.get('comment')
    if not content:
        flash('Comment cannot be empty.')
        return redirect(url_for('main.dashboard'))

    comment = Comment(
        content=content,
        user_id=current_user.id,
        file_id=None,  # general comment
        timestamp=datetime.utcnow()
    )
    db.session.add(comment)
    db.session.commit()
    flash('✅ General comment posted.')
    return redirect(url_for('main.dashboard'))

@comments.route('/delete_comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id and current_user.role != 'admin':
        flash('No permission to delete.')
        return redirect(url_for('main.dashboard'))

    db.session.delete(comment)
    db.session.commit()
    flash('🗑️ Comment deleted.')
    return redirect(url_for('main.dashboard'))
