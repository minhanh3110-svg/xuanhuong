from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from app import db, User, UserActivity, mail
from flask_mail import Message
import pyotp
import qrcode
import io
import base64
from functools import wraps

auth = Blueprint('auth', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Bạn không có quyền truy cập trang này.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.', 'error')
            return redirect(url_for('auth.register'))
            
        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã tồn tại.', 'error')
            return redirect(url_for('auth.register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email đã được sử dụng.', 'error')
            return redirect(url_for('auth.register'))
            
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=generate_password_hash(password),
            role='user'
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Gửi email xác nhận
        token = user.generate_confirmation_token()
        confirm_url = url_for('auth.confirm_email', token=token, _external=True)
        msg = Message('Xác nhận đăng ký tài khoản',
                     recipients=[user.email])
        msg.html = render_template('auth/email/confirm.html',
                                 user=user,
                                 confirm_url=confirm_url)
        mail.send(msg)
        
        flash('Đăng ký thành công! Vui lòng kiểm tra email để xác nhận tài khoản.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html')

@auth.route('/confirm/<token>')
def confirm_email(token):
    user = User.verify_confirmation_token(token)
    if not user:
        flash('Liên kết xác nhận không hợp lệ hoặc đã hết hạn.', 'error')
        return redirect(url_for('auth.login'))
        
    if user.is_active:
        flash('Tài khoản đã được xác nhận.', 'info')
        return redirect(url_for('auth.login'))
        
    user.is_active = True
    user.log_activity('confirm_email')
    db.session.commit()
    
    flash('Xác nhận email thành công! Bạn có thể đăng nhập ngay bây giờ.', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        if 'otp_code' in request.form:
            username = request.form.get('username')
            otp_code = request.form.get('otp_code')
            user = User.query.filter_by(username=username).first()
            
            if user and user.verify_otp(otp_code):
                login_user(user)
                user.last_login = datetime.utcnow()
                user.log_activity('login')
                db.session.commit()
                
                next_page = session.get('next', url_for('index'))
                session.pop('next', None)
                return redirect(next_page)
            else:
                flash('Mã xác thực không chính xác.', 'error')
                return render_template('auth/login.html', show_otp=True, username=username)
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            remember = 'remember' in request.form
            
            user = User.query.filter_by(username=username).first()
            
            if user and check_password_hash(user.password_hash, password):
                if not user.is_active:
                    flash('Tài khoản chưa được kích hoạt.', 'warning')
                    return redirect(url_for('auth.login'))
                    
                if user.otp_enabled:
                    session['next'] = request.args.get('next')
                    return render_template('auth/login.html', show_otp=True, username=username)
                    
                login_user(user, remember=remember)
                user.last_login = datetime.utcnow()
                user.log_activity('login')
                db.session.commit()
                
                next_page = request.args.get('next', url_for('index'))
                return redirect(next_page)
            else:
                flash('Tên đăng nhập hoặc mật khẩu không chính xác.', 'error')
    
    return render_template('auth/login.html', show_otp=False)

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = user.generate_reset_token()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            msg = Message('Đặt lại mật khẩu',
                         recipients=[user.email])
            msg.html = render_template('auth/email/reset_password.html',
                                     user=user,
                                     reset_url=reset_url)
            mail.send(msg)
            
        flash('Hướng dẫn đặt lại mật khẩu đã được gửi đến email của bạn.', 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/forgot_password.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    user = User.query.filter_by(reset_password_token=token).first()
    if not user or not user.verify_reset_token():
        flash('Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.', 'error')
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.', 'error')
            return redirect(url_for('auth.reset_password', token=token))
            
        user.password_hash = generate_password_hash(password)
        user.clear_reset_token()
        user.log_activity('password_reset')
        db.session.commit()
        
        flash('Đặt lại mật khẩu thành công! Bạn có thể đăng nhập ngay bây giờ.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', token=token)

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.phone = request.form.get('phone')
        current_user.department = request.form.get('department')
        current_user.position = request.form.get('position')
        
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if current_password and new_password and confirm_password:
            if not check_password_hash(current_user.password_hash, current_password):
                flash('Mật khẩu hiện tại không chính xác.', 'error')
                return redirect(url_for('auth.profile'))
                
            if new_password != confirm_password:
                flash('Mật khẩu mới xác nhận không khớp.', 'error')
                return redirect(url_for('auth.profile'))
                
            current_user.password_hash = generate_password_hash(new_password)
            current_user.log_activity('password_change')
            
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file.filename:
                # Xử lý upload ảnh đại diện
                pass
                
        current_user.log_activity('profile_update')
        db.session.commit()
        flash('Cập nhật thông tin thành công!', 'success')
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/profile.html')

@auth.route('/activity-log')
@login_required
def activity_log():
    page = request.args.get('page', 1, type=int)
    activities = UserActivity.query.filter_by(user_id=current_user.id)\
        .order_by(UserActivity.timestamp.desc())\
        .paginate(page=page, per_page=10)
    return render_template('auth/activity_log.html', activities=activities)

@auth.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    if current_user.otp_enabled:
        flash('Xác thực hai lớp đã được bật.', 'info')
        return redirect(url_for('auth.profile'))
        
    if not current_user.otp_secret:
        current_user.otp_secret = pyotp.random_base32()
        db.session.commit()
        
    if request.method == 'POST':
        otp_code = request.form.get('otp_code')
        if current_user.verify_otp(otp_code):
            current_user.otp_enabled = True
            current_user.log_activity('2fa_enable')
            db.session.commit()
            flash('Bật xác thực hai lớp thành công!', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash('Mã xác thực không chính xác.', 'error')
            
    # Tạo QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(current_user.get_otp_uri())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Chuyển QR code thành base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_code = base64.b64encode(buffer.getvalue()).decode()
    
    return render_template('auth/setup_2fa.html',
                         qr_code=qr_code,
                         secret_key=current_user.otp_secret)

@auth.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    if not current_user.otp_enabled:
        flash('Xác thực hai lớp chưa được bật.', 'info')
        return redirect(url_for('auth.profile'))
        
    current_user.otp_enabled = False
    current_user.otp_secret = None
    current_user.log_activity('2fa_disable')
    db.session.commit()
    
    flash('Đã tắt xác thực hai lớp.', 'success')
    return redirect(url_for('auth.profile'))

@auth.route('/manage-users')
@login_required
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    role = request.args.get('role', '')
    status = request.args.get('status', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.full_name.ilike(f'%{search}%'))
        )
    
    if role:
        query = query.filter_by(role=role)
        
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
        
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=10)
    return render_template('auth/manage_users.html', users=users)

@auth.route('/edit-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user == current_user:
        flash('Không thể chỉnh sửa tài khoản của chính mình.', 'error')
        return redirect(url_for('auth.manage_users'))
        
    user.role = request.form.get('role')
    user.is_active = 'is_active' in request.form
    
    current_user.log_activity(
        'edit_user',
        f'Chỉnh sửa người dùng: {user.username}'
    )
    db.session.commit()
    
    flash('Cập nhật người dùng thành công!', 'success')
    return redirect(url_for('auth.manage_users'))

@auth.route('/approve-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.is_active:
        flash('Người dùng đã được kích hoạt.', 'info')
        return redirect(url_for('auth.manage_users'))
        
    user.is_active = True
    current_user.log_activity(
        'approve_user',
        f'Kích hoạt người dùng: {user.username}'
    )
    db.session.commit()
    
    # Gửi email thông báo
    msg = Message('Tài khoản đã được kích hoạt',
                 recipients=[user.email])
    msg.html = render_template('auth/email/account_approved.html', user=user)
    mail.send(msg)
    
    flash('Kích hoạt người dùng thành công!', 'success')
    return redirect(url_for('auth.manage_users'))

@auth.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user == current_user:
        flash('Không thể xóa tài khoản của chính mình.', 'error')
        return redirect(url_for('auth.manage_users'))
        
    username = user.username
    db.session.delete(user)
    current_user.log_activity(
        'delete_user',
        f'Xóa người dùng: {username}'
    )
    db.session.commit()
    
    flash('Xóa người dùng thành công!', 'success')
    return redirect(url_for('auth.manage_users'))

@auth.route('/logout')
@login_required
def logout():
    current_user.log_activity('logout')
    logout_user()
    flash('Đã đăng xuất thành công.', 'success')
    return redirect(url_for('auth.login'))
