from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

# ─────────────────────────────────────────────────────────────
# Association table for many-to-many relationship: Task ↔ File
# ─────────────────────────────────────────────────────────────
task_files = db.Table(
    'task_files',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id'), primary_key=True),
    db.Column('file_id', db.Integer, db.ForeignKey('file.id'), primary_key=True)
)

# ─────────────────────────────────────────────
# Many-to-many association table for Comment ↔ File
# ─────────────────────────────────────────────
comment_files = db.Table(
    'comment_files',
    db.Column('comment_id', db.Integer, db.ForeignKey('comment.id'), primary_key=True),
    db.Column('file_id', db.Integer, db.ForeignKey('file.id'), primary_key=True)
)

# ─────────────────────────────────────────────────────────────
# User Model
# ─────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='Administrative Assistant', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    files = db.relationship('File', backref='uploader', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    assigned_tasks_rel = db.relationship('Task', foreign_keys='Task.assigned_to_id', backref='assigned_to', lazy=True)
    created_tasks_rel = db.relationship('Task', foreign_keys='Task.created_by_id', backref='creator', lazy=True)

    # Password methods
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        try:
            return check_password_hash(self.password, password)
        except ValueError:
            return self.password == password

    # Role helpers
    def is_admin(self): return self.role == "Admin"
    def is_manager(self): return self.role == "Department Manager"
    def is_officer(self): return self.role == "Department Officer"
    def is_supervisor(self): return self.role == "Department Supervisor"
    def is_staff(self): return self.role == "Administrative Assistant"

    def can_assign_task_to(self, other_user):
        """
        Task assignment permissions:

        - Admin → anyone
        - Department Manager → Officers, Supervisors, Administrative Assistant
        - Department Officer → Supervisors, Administrative Assistant
        - Department Supervisor → Administrative Assistant
        - Administrative Assistant → cannot assign
        """
        if self.is_admin():
            return True
        elif self.is_manager():
            return other_user.role in ["Department Officer", "Department Supervisor", "Administrative Assistant"]
        elif self.is_officer():
            return other_user.role in ["Department Supervisor", "Administrative Assistant"]
        elif self.is_supervisor():
            return other_user.is_staff()
        return False

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

# ─────────────────────────────────────────────────────────────
# File Model
# ─────────────────────────────────────────────────────────────
class File(db.Model):
    __tablename__ = "file"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Removed direct foreign keys to avoid conflicts with many-to-many relationships
    # task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)
    # comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)

    # Many-to-many relationships
    tasks = db.relationship('Task', secondary=task_files, back_populates='files')
    comments = db.relationship('Comment', secondary=comment_files, back_populates='files')

    def __repr__(self):
        return f"<File {self.original_filename}>"

# ─────────────────────────────────────────────────────────────
# Comment Model
# ─────────────────────────────────────────────────────────────
class Comment(db.Model):
    __tablename__ = "comment"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

    # Removed redundant relationship definition
    # user = db.relationship('User', backref='comments', lazy=True)

    # Files attached to this comment
    files = db.relationship('File', secondary=comment_files, back_populates='comments')

    def __repr__(self):
        return f"<Comment {self.id} on Task {self.task_id}>"

# ─────────────────────────────────────────────────────────────
# Notification Model
# ─────────────────────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # relationship back to user
    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))

    def __repr__(self):
        return f"<Notification to user {self.user_id}: {self.message[:40]}>"

# ─────────────────────────────────────────────────────────────
# Task Category Model (Admin-Managed)
# ─────────────────────────────────────────────────────────────
class TaskCategory(db.Model):
    __tablename__ = "task_category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.String(255))

    # One category → many tasks
    tasks = db.relationship('Task', back_populates='category')

    def __repr__(self):
        return f"<TaskCategory {self.name}>"

# ─────────────────────────────────────────────────────────────
# Task Model
# ─────────────────────────────────────────────────────────────
class Task(db.Model):
    __tablename__ = "task"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)

    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Link to admin-managed category
    category_id = db.Column(db.Integer, db.ForeignKey('task_category.id'))
    category = db.relationship('TaskCategory', back_populates='tasks')

    files = db.relationship('File', secondary=task_files, back_populates='tasks')
    comments = db.relationship('Comment', backref='task', lazy=True)

    def __repr__(self):
        return f"<Task {self.title} (Status: {self.status})>"