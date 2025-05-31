from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
import os
import logging
from logging.handlers import RotatingFileHandler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import pyotp
import qrcode
import io
import base64
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask_mail import Mail, Message
import secrets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Cấu hình logging
if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

# Khởi tạo Flask app
app = Flask(__name__)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Khởi động ứng dụng')

# Cấu hình Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
mail = Mail(app)

# Cấu hình Rate Limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Cấu hình database
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db = SQLAlchemy(app)

# Cấu hình Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Vui lòng đăng nhập để truy cập trang này.'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    department = db.Column(db.String(100))
    position = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    otp_secret = db.Column(db.String(32))
    otp_enabled = db.Column(db.Boolean, default=False)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    activities = db.relationship('UserActivity', backref='user', lazy=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    avatar_url = db.Column(db.String(200))
    reset_password_token = db.Column(db.String(100), unique=True)
    reset_password_expires = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def get_otp_uri(self):
        if self.otp_secret:
            return pyotp.totp.TOTP(self.otp_secret).provisioning_uri(
                name=self.username,
                issuer_name="Hệ thống Quản lý Nuôi Cấy Mô"
            )
        return None

    def verify_otp(self, otp_code):
        if self.otp_secret and self.otp_enabled:
            totp = pyotp.TOTP(self.otp_secret)
            return totp.verify(otp_code)
        return True

    def has_permission(self, permission):
        permissions = {
            'admin': ['manage_users', 'manage_samples', 'manage_rooms', 'view_reports', 'approve_users'],
            'manager': ['manage_samples', 'manage_rooms', 'view_reports'],
            'researcher': ['manage_samples', 'view_reports'],
            'user': ['view_samples']
        }
        return permission in permissions.get(self.role, [])

    def generate_confirmation_token(self):
        s = Serializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_confirmation_token(token, expiration=3600):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expiration)
        except:
            return None
        return User.query.get(data['user_id'])

    def generate_reset_token(self):
        self.reset_password_token = secrets.token_urlsafe(32)
        self.reset_password_expires = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()
        return self.reset_password_token

    def verify_reset_token(self):
        if not self.reset_password_token or not self.reset_password_expires:
            return False
        if datetime.utcnow() > self.reset_password_expires:
            return False
        return True

    def clear_reset_token(self):
        self.reset_password_token = None
        self.reset_password_expires = None
        db.session.commit()

    def log_activity(self, action, details=None):
        activity = UserActivity(
            user_id=self.id,
            action=action,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(activity)
        db.session.commit()

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def action_text(self):
        actions = {
            'login': 'Đăng nhập',
            'logout': 'Đăng xuất',
            'profile_update': 'Cập nhật thông tin',
            'password_change': 'Đổi mật khẩu',
            'password_reset': 'Khôi phục mật khẩu',
            '2fa_enable': 'Bật xác thực 2 lớp',
            '2fa_disable': 'Tắt xác thực 2 lớp'
        }
        return actions.get(self.action, self.action)

class Mau(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ma_mau = db.Column(db.String(50), unique=True, nullable=False)
    ten = db.Column(db.String(100), nullable=False)
    mo_ta = db.Column(db.Text)
    ngay_cay = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    trang_thai = db.Column(db.String(50))
    phong_id = db.Column(db.Integer, db.ForeignKey('phong.id'), nullable=False)
    nhat_ky = db.relationship('NhatKy', backref='mau', lazy=True)

class Phong(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ten = db.Column(db.String(100), nullable=False)
    nhiet_do = db.Column(db.Float)
    do_am = db.Column(db.Float)
    mau_list = db.relationship('Mau', backref='phong', lazy=True)

class NhatKy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mau_id = db.Column(db.Integer, db.ForeignKey('mau.id'), nullable=False)
    ngay_ghi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    noi_dung = db.Column(db.Text, nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50))  # 'alert', 'warning', 'info'
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    
    @staticmethod
    def create_temp_alert(phong_id, temp, humidity):
        phong = Phong.query.get(phong_id)
        if not phong:
            return
        
        if temp > 30 or temp < 15 or humidity > 80 or humidity < 40:
            users = User.query.filter_by(role='admin').all()
            for user in users:
                notif = Notification(
                    user_id=user.id,
                    title=f'Cảnh báo điều kiện môi trường - Phòng {phong.ten}',
                    message=f'Nhiệt độ: {temp}°C, Độ ẩm: {humidity}%',
                    type='alert'
                )
                db.session.add(notif)
            db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Template filters
@app.template_filter('status_color')
def status_color(status):
    colors = {
        'Mới tạo': 'success',
        'Đang phát triển': 'primary',
        'Đã hoàn thành': 'warning',
        'Thất bại': 'danger'
    }
    return colors.get(status, 'secondary')

# Trang chủ
@app.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 9
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    room = request.args.get('room', '')

    query = Mau.query
    if search:
        query = query.filter(Mau.ten.ilike(f'%{search}%'))
    if status:
        query = query.filter(Mau.trang_thai == status)
    if room:
        query = query.filter(Mau.phong_id == room)

    stats = {
        'new_count': Mau.query.filter_by(trang_thai='Mới tạo').count(),
        'developing_count': Mau.query.filter_by(trang_thai='Đang phát triển').count(),
        'completed_count': Mau.query.filter_by(trang_thai='Đã hoàn thành').count(),
        'failed_count': Mau.query.filter_by(trang_thai='Thất bại').count()
    }

    room_stats = db.session.query(
        Phong.ten.label('name'),
        func.count(Mau.id).label('count')
    ).outerjoin(Mau).group_by(Phong.id, Phong.ten).all()

    mau_pagination = query.order_by(Mau.ngay_cay.desc()).paginate(page=page, per_page=per_page)
    rooms = Phong.query.all()

    return render_template('index.html', mau_pagination=mau_pagination, stats=stats, room_stats=room_stats, rooms=rooms)

@app.route('/them-mau-moi', methods=['GET', 'POST'])
@login_required
def them_mau_moi():
    if request.method == 'POST':
        ma_mau = request.form.get('ma_mau')
        ten = request.form.get('ten')
        mo_ta = request.form.get('mo_ta')
        phong_id = request.form.get('phong_id')

        if not all([ma_mau, ten, phong_id]):
            flash('Vui lòng điền đầy đủ thông tin bắt buộc', 'error')
            return redirect(url_for('them_mau_moi'))

        try:
            mau_moi = Mau(ma_mau=ma_mau, ten=ten, mo_ta=mo_ta, phong_id=phong_id, trang_thai='Mới tạo')
            db.session.add(mau_moi)
            db.session.commit()
            flash('Thêm mẫu mới thành công!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')

    phong_list = Phong.query.all()
    return render_template('them_mau_moi.html', phong_list=phong_list)

@app.route('/chi-tiet-mau/<int:id>')
@login_required
def chi_tiet_mau(id):
    mau = Mau.query.get_or_404(id)
    return render_template('chi_tiet_mau.html', mau=mau)

@app.route('/cap-nhat-mau/<int:id>', methods=['GET', 'POST'])
@login_required
def cap_nhat_mau(id):
    mau = Mau.query.get_or_404(id)
    if request.method == 'POST':
        try:
            mau.ten = request.form.get('ten')
            mau.mo_ta = request.form.get('mo_ta')
            mau.trang_thai = request.form.get('trang_thai')
            mau.phong_id = request.form.get('phong_id')
            db.session.commit()
            flash('Cập nhật mẫu thành công!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')

    phong_list = Phong.query.all()
    return render_template('cap_nhat_mau.html', mau=mau, phong_list=phong_list)

@app.route('/xoa-mau/<int:id>')
@login_required
def xoa_mau(id):
    if current_user.role != 'admin':
        flash('Bạn không có quyền xóa mẫu!', 'error')
        return redirect(url_for('index'))

    mau = Mau.query.get_or_404(id)
    try:
        db.session.delete(mau)
        db.session.commit()
        flash('Xóa mẫu thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')

    return redirect(url_for('index'))

@app.route('/phong-moi-truong')
@login_required
def phong_moi_truong():
    phong_list = Phong.query.all()
    return render_template('phong_moi_truong.html', phong_list=phong_list)

@app.route('/them-phong-moi', methods=['GET', 'POST'])
@login_required
def them_phong_moi():
    if request.method == 'POST':
        ten_phong = request.form.get('ten_phong')
        nhiet_do = request.form.get('nhiet_do')
        do_am = request.form.get('do_am')

        if not ten_phong:
            flash('Vui lòng nhập tên phòng', 'error')
            return redirect(url_for('them_phong_moi'))

        try:
            phong_moi = Phong(ten=ten_phong, nhiet_do=float(nhiet_do) if nhiet_do else None, do_am=float(do_am) if do_am else None)
            db.session.add(phong_moi)
            db.session.commit()
            flash('Thêm phòng mới thành công!', 'success')
            return redirect(url_for('phong_moi_truong'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')

    return render_template('them_phong_moi.html')

@app.route('/them-nhat-ky/<int:mau_id>', methods=['POST'])
@login_required
def them_nhat_ky(mau_id):
    noi_dung = request.form.get('noi_dung')
    if not noi_dung:
        flash('Vui lòng nhập nội dung nhật ký', 'error')
        return redirect(url_for('chi_tiet_mau', id=mau_id))

    try:
        nhat_ky = NhatKy(mau_id=mau_id, noi_dung=noi_dung)
        db.session.add(nhat_ky)
        db.session.commit()
        flash('Thêm nhật ký thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')

    return redirect(url_for('chi_tiet_mau', id=mau_id))

@app.route('/api/cap-nhat-moi-truong/<int:phong_id>', methods=['POST'])
@login_required
def cap_nhat_moi_truong(phong_id):
    if not request.is_json:
        return jsonify({'status': 'error', 'message': 'Yêu cầu phải là JSON'}), 400

    phong = Phong.query.get_or_404(phong_id)
    data = request.get_json()

    try:
        nhiet_do = data.get('nhiet_do')
        do_am = data.get('do_am')

        if nhiet_do is None or do_am is None:
            return jsonify({
                'status': 'error',
                'message': 'Thiếu thông tin nhiệt độ hoặc độ ẩm'
            }), 400

        # Validate ranges
        if not (-50 <= float(nhiet_do) <= 100):
            return jsonify({
                'status': 'error',
                'message': 'Nhiệt độ không hợp lệ'
            }), 400

        if not (0 <= float(do_am) <= 100):
            return jsonify({
                'status': 'error',
                'message': 'Độ ẩm không hợp lệ'
            }), 400

        phong.nhiet_do = float(nhiet_do)
        phong.do_am = float(do_am)
        
        # Create notification if needed
        Notification.create_temp_alert(phong_id, float(nhiet_do), float(do_am))
        
        db.session.commit()
        return jsonify({
            'status': 'success',
            'data': {
                'nhiet_do': phong.nhiet_do,
                'do_am': phong.do_am
            }
        })
    except ValueError:
        return jsonify({
            'status': 'error',
            'message': 'Giá trị nhiệt độ hoặc độ ẩm không hợp lệ'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Lỗi hệ thống: {str(e)}'
        }), 500

@app.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=10
    )
    return render_template('notifications.html', notifications=notifications)

@app.route('/mark-notification-read/<int:notif_id>')
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        flash('Không có quyền truy cập thông báo này', 'error')
        return redirect(url_for('notifications'))
    
    notif.read = True
    db.session.commit()
    return redirect(url_for('notifications'))

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        unread_count = Notification.query.filter_by(
            user_id=current_user.id,
            read=False
        ).count()
        return {'unread_notifications': unread_count}
    return {'unread_notifications': 0}

# Register blueprints
from auth import auth as auth_blueprint
app.register_blueprint(auth_blueprint, url_prefix='/auth')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
