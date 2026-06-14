import os
import re
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# ------------------------------------------------------------------
# App configuration
# ------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this')

database_url = os.environ.get('DATABASE_URL', 'sqlite:///social.db')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------
class User(UserMixin, db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    username    = db.Column(db.String(64),  unique=True, nullable=False)
    email       = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role        = db.Column(db.String(10), default='user')   # 'user' or 'admin'
    created_at  = db.Column(db.DateTime,  default=datetime.utcnow)

    posts = db.relationship('Post', backref='author', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'


class Friendship(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status    = db.Column(db.String(10), default='pending')   # pending / accepted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requester = db.relationship('User', foreign_keys=[user_id])
    receiver  = db.relationship('User', foreign_keys=[friend_id])


class Post(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    visibility = db.Column(db.String(10), default='public')   # public / friends
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    likes    = db.relationship('Like',    backref='post', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')


class Like(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', name='unique_like'),)


class Comment(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    post_id    = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content    = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def valid_email(email):
    return bool(EMAIL_RE.match(email))


def are_friends(user_id_a, user_id_b):
    return Friendship.query.filter(
        db.or_(
            db.and_(Friendship.user_id == user_id_a, Friendship.friend_id == user_id_b),
            db.and_(Friendship.user_id == user_id_b, Friendship.friend_id == user_id_a)
        ),
        Friendship.status == 'accepted'
    ).first() is not None


def get_friend_ids(user_id):
    rows = Friendship.query.filter(
        db.or_(Friendship.user_id == user_id, Friendship.friend_id == user_id),
        Friendship.status == 'accepted'
    ).all()
    ids = set()
    for r in rows:
        ids.add(r.user_id if r.user_id != user_id else r.friend_id)
    return ids


# ------------------------------------------------------------------
# Auth routes
# ------------------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        if not valid_email(email):
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'danger')
            return redirect(url_for('register'))

        role = 'admin' if User.query.count() == 0 else 'user'
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Account created. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))

    if request.method == 'POST':
        login_input = request.form.get('login', '').strip()
        password    = request.form.get('password', '')

        # Allow login by username OR email
        user = User.query.filter_by(username=login_input).first() or \
               User.query.filter_by(email=login_input.lower()).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('feed'))

        flash('Invalid username/email or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ------------------------------------------------------------------
# Feed routes
# ------------------------------------------------------------------
@app.route('/')
@login_required
def feed():
    view = request.args.get('view', 'public')

    if view == 'friends':
        friend_ids = get_friend_ids(current_user.id)
        friend_ids.add(current_user.id)
        posts = Post.query.filter(Post.user_id.in_(friend_ids)).order_by(Post.created_at.desc()).all()
    else:
        view = 'public'
        posts = Post.query.filter_by(visibility='public').order_by(Post.created_at.desc()).all()

    return render_template('feed.html', posts=posts, view=view, are_friends=are_friends)


@app.route('/post', methods=['POST'])
@login_required
def create_post():
    content    = request.form.get('content', '').strip()
    visibility = request.form.get('visibility', 'public')

    if visibility not in ('public', 'friends'):
        visibility = 'public'

    if content:
        post = Post(user_id=current_user.id, content=content, visibility=visibility)
        db.session.add(post)
        db.session.commit()
        flash('Post created.', 'success')
    else:
        flash('Post cannot be empty.', 'danger')

    return redirect(url_for('feed'))


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and not current_user.is_admin():
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'success')
    return redirect(request.referrer or url_for('feed'))


@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post     = Post.query.get_or_404(post_id)
    existing = Like.query.filter_by(post_id=post.id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Like(post_id=post.id, user_id=current_user.id))
    db.session.commit()
    return redirect(request.referrer or url_for('feed'))


@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def comment_post(post_id):
    post    = Post.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    if content:
        db.session.add(Comment(post_id=post.id, user_id=current_user.id, content=content))
        db.session.commit()
    return redirect(request.referrer or url_for('feed'))


@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id and not current_user.is_admin():
        abort(403)
    db.session.delete(comment)
    db.session.commit()
    return redirect(request.referrer or url_for('feed'))


# ------------------------------------------------------------------
# Friend routes
# ------------------------------------------------------------------
@app.route('/friends')
@login_required
def friends():
    friend_ids = get_friend_ids(current_user.id)
    friend_list = User.query.filter(User.id.in_(friend_ids)).all() if friend_ids else []
    incoming    = Friendship.query.filter_by(friend_id=current_user.id, status='pending').all()
    outgoing    = Friendship.query.filter_by(user_id=current_user.id,   status='pending').all()

    excluded_ids  = {current_user.id} | friend_ids
    excluded_ids |= {f.friend_id for f in outgoing}
    excluded_ids |= {f.user_id   for f in incoming}
    other_users   = User.query.filter(~User.id.in_(excluded_ids)).all()

    return render_template(
        'friends.html',
        friend_list=friend_list,
        incoming=incoming,
        outgoing=outgoing,
        other_users=other_users
    )


@app.route('/friends/request/<int:user_id>', methods=['POST'])
@login_required
def send_friend_request(user_id):
    if user_id == current_user.id:
        abort(400)
    target   = User.query.get_or_404(user_id)
    existing = Friendship.query.filter(
        db.or_(
            db.and_(Friendship.user_id == current_user.id, Friendship.friend_id == user_id),
            db.and_(Friendship.user_id == user_id,         Friendship.friend_id == current_user.id)
        )
    ).first()
    if not existing:
        db.session.add(Friendship(user_id=current_user.id, friend_id=user_id, status='pending'))
        db.session.commit()
        flash(f'Friend request sent to {target.username}.', 'success')
    return redirect(url_for('friends'))


@app.route('/friends/accept/<int:request_id>', methods=['POST'])
@login_required
def accept_friend_request(request_id):
    fr = Friendship.query.get_or_404(request_id)
    if fr.friend_id != current_user.id:
        abort(403)
    fr.status = 'accepted'
    db.session.commit()
    flash('Friend request accepted.', 'success')
    return redirect(url_for('friends'))


@app.route('/friends/decline/<int:request_id>', methods=['POST'])
@login_required
def decline_friend_request(request_id):
    fr = Friendship.query.get_or_404(request_id)
    if fr.friend_id != current_user.id and fr.user_id != current_user.id:
        abort(403)
    db.session.delete(fr)
    db.session.commit()
    flash('Friend request removed.', 'success')
    return redirect(url_for('friends'))


@app.route('/friends/unfriend/<int:user_id>', methods=['POST'])
@login_required
def unfriend(user_id):
    fr = Friendship.query.filter(
        db.or_(
            db.and_(Friendship.user_id == current_user.id, Friendship.friend_id == user_id),
            db.and_(Friendship.user_id == user_id,         Friendship.friend_id == current_user.id)
        ),
        Friendship.status == 'accepted'
    ).first()
    if fr:
        db.session.delete(fr)
        db.session.commit()
        flash('Friend removed.', 'success')
    return redirect(url_for('friends'))


# ------------------------------------------------------------------
# Admin routes
# ------------------------------------------------------------------
def admin_required():
    if not current_user.is_authenticated or not current_user.is_admin():
        abort(403)


@app.route('/admin')
@login_required
def admin_dashboard():
    admin_required()
    stats = {
        'total_users':       User.query.count(),
        'total_posts':       Post.query.count(),
        'total_comments':    Comment.query.count(),
        'total_friendships': Friendship.query.filter_by(status='accepted').count(),
    }
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin.html', stats=stats, users=users)


@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    admin_required()
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin_dashboard'))
    user = User.query.get_or_404(user_id)
    Friendship.query.filter(
        db.or_(Friendship.user_id == user.id, Friendship.friend_id == user.id)
    ).delete()
    Like.query.filter_by(user_id=user.id).delete()
    Comment.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{user.username}" deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
def admin_toggle_role(user_id):
    admin_required()
    if user_id == current_user.id:
        flash('You cannot change your own role.', 'danger')
        return redirect(url_for('admin_dashboard'))
    user = User.query.get_or_404(user_id)
    user.role = 'user' if user.role == 'admin' else 'admin'
    db.session.commit()
    flash(f'"{user.username}" is now {user.role}.', 'success')
    return redirect(url_for('admin_dashboard'))


# ------------------------------------------------------------------
# Error handlers
# ------------------------------------------------------------------
@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403, message='Forbidden'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404, message='Not Found'), 404


# ------------------------------------------------------------------
# Startup: create tables
# ------------------------------------------------------------------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
