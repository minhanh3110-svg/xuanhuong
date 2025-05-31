from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db, User, mail, UserActivity
from flask_mail import Message
from functools import wraps
import pyotp
import qrcode
import io
import base64

auth = Blueprint('auth', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Bạn không có quyền truy cập trang này.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([username, email, full_name, password, confirm_password]):
            flash('Vui lòng điền đầy đủ thông tin.', 'danger')
            return redirect(url_for('auth.register'))

        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã tồn tại.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash('Email đã được sử dụng.', 'danger')
            return redirect(url_for('auth.register'))

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            otp_secret=pyotp.random_base32()
        )
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()

            token = user.generate_confirmation_token()
            confirm_url = url_for('auth.confirm_email', token=token, _external=True)
            
            msg = Message('Xác nhận tài khoản',
                        recipients=[user.email])
            msg.html = render_template('email/confirm.html',
                                     user=user,
                                     confirm_url=confirm_url)
            mail.send(msg)

            flash('Đăng ký thành công! Vui lòng kiểm tra email để xác nhận tài khoản.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return redirect(url_for('auth.register'))

    return render_template('auth/register.html')

@auth.route('/confirm/<token>')
def confirm_email(token):
    user = User.verify_confirmation_token(token)
    if user is None:
        flash('Link xác nhận không hợp lệ hoặc đã hết hạn.', 'danger')
        return redirect(url_for('auth.login'))
    
    if user.is_active:
        flash('Tài khoản đã được xác nhận trước đó.', 'info')
        return redirect(url_for('auth.login'))
    
    user.is_active = True
    db.session.commit()
    flash('Xác nhận tài khoản thành công! Bạn có thể đăng nhập ngay bây giờ.', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        otp_code = request.form.get('otp_code')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Tài khoản chưa được kích hoạt. Vui lòng kiểm tra email để xác nhận.', 'warning')
                return redirect(url_for('auth.login'))

            if user.otp_enabled and not otp_code:
                # Hiển thị form nhập OTP
                return render_template('auth/login.html', show_otp=True, username=username)

            if user.otp_enabled and not user.verify_otp(otp_code):
                flash('Mã OTP không chính xác.', 'danger')
                return render_template('auth/login.html', show_otp=True, username=username)

            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            user.log_activity('login')
            db.session.commit()

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không chính xác.', 'danger')

    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    current_user.log_activity('logout')
    logout_user()
    flash('Đăng xuất thành công.', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/profile')
@login_required
def profile():
    if current_user.otp_enabled:
        otp_uri = current_user.get_otp_uri()
        img = qrcode.make(otp_uri)
        buffered = io.BytesIO()
        img.save(buffered)
        qr_code = base64.b64encode(buffered.getvalue()).decode()
    else:
        qr_code = None
    
    return render_template('auth/profile.html', qr_code=qr_code)

@auth.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.department = request.form.get('department')
        current_user.position = request.form.get('position')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')
        
        try:
            current_user.log_activity('profile_update')
            db.session.commit()
            flash('Cập nhật thông tin thành công!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
        
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/edit_profile.html')

@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(current_password):
            flash('Mật khẩu hiện tại không chính xác.', 'danger')
            return redirect(url_for('auth.change_password'))

        if new_password != confirm_password:
            flash('Mật khẩu mới không khớp.', 'danger')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(new_password)
        current_user.log_activity('password_change')
        db.session.commit()
        flash('Đổi mật khẩu thành công!', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/change_password.html')

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = user.generate_reset_token()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            msg = Message('Khôi phục mật khẩu',
                        recipients=[user.email])
            msg.html = render_template('email/reset_password.html',
                                     user=user,
                                     reset_url=reset_url)
            mail.send(msg)
            
            flash('Hướng dẫn khôi phục mật khẩu đã được gửi đến email của bạn.', 'info')
            return redirect(url_for('auth.login'))
        
        flash('Không tìm thấy tài khoản với email này.', 'danger')
    
    return render_template('auth/forgot_password.html')

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_password_token=token).first()
    
    if not user or not user.verify_reset_token():
        flash('Link khôi phục mật khẩu không hợp lệ hoặc đã hết hạn.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        user.set_password(password)
        user.clear_reset_token()
        user.log_activity('password_reset')
        db.session.commit()
        
        flash('Đặt lại mật khẩu thành công! Bạn có thể đăng nhập ngay bây giờ.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html')

@auth.route('/enable-2fa', methods=['POST'])
@login_required
def enable_2fa():
    current_user.otp_enabled = True
    current_user.log_activity('2fa_enable')
    db.session.commit()
    flash('Xác thực hai lớp đã được bật.', 'success')
    return redirect(url_for('auth.profile'))

@auth.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    current_user.otp_enabled = False
    current_user.log_activity('2fa_disable')
    db.session.commit()
    flash('Xác thực hai lớp đã được tắt.', 'success')
    return redirect(url_for('auth.profile'))

@auth.route('/activity-log')
@login_required
def activity_log():
    page = request.args.get('page', 1, type=int)
    activities = UserActivity.query.filter_by(user_id=current_user.id)\
        .order_by(UserActivity.timestamp.desc())\
        .paginate(page=page, per_page=10)
    return render_template('auth/activity_log.html', activities=activities)

@auth.route('/manage-users')
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    role = request.args.get('role', '')
    
    query = User.query
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.full_name.ilike(f'%{search}%'))
        )
    if role:
        query = query.filter_by(role=role)
    
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=10)
    return render_template('auth/manage_users.html', users=users)

@auth.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    departments = ['Phòng Nghiên cứu', 'Phòng Thí nghiệm', 'Phòng Quản lý', 'Phòng Kỹ thuật']
    positions = ['Trưởng phòng', 'Phó phòng', 'Nghiên cứu viên', 'Kỹ thuật viên', 'Nhân viên']
    roles = ['admin', 'manager', 'researcher', 'user']
    
    if request.method == 'POST':
        try:
            user.full_name = request.form.get('full_name')
            user.email = request.form.get('email')
            user.department = request.form.get('department')
            user.position = request.form.get('position')
            user.role = request.form.get('role')
            user.is_active = 'is_active' in request.form
            
            db.session.commit()
            flash('Cập nhật thông tin người dùng thành công!', 'success')
            return redirect(url_for('auth.manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
    
    return render_template('auth/edit_user.html', 
                         user=user,
                         departments=departments,
                         positions=positions,
                         roles=roles)

@auth.route('/delete-user/<int:user_id>')
@admin_required
def delete_user(user_id):
    if current_user.id == user_id:
        flash('Không thể xóa tài khoản của chính mình.', 'danger')
        return redirect(url_for('auth.manage_users'))
    
    user = User.query.get_or_404(user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash('Xóa người dùng thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
    
    return redirect(url_for('auth.manage_users'))
