from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import db, User, mail, UserActivity
from flask_mail import Message
from functools import wraps

auth = Blueprint('auth', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Bạn không có quyền truy cập trang này', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        password = request.form.get('password')
        department = request.form.get('department')
        position = request.form.get('position')

        # Kiểm tra dữ liệu
        if not all([username, email, full_name, password]):
            flash('Vui lòng điền đầy đủ thông tin bắt buộc', 'error')
            return redirect(url_for('auth.register'))

        # Kiểm tra username và email đã tồn tại chưa
        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã được sử dụng', 'error')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash('Email đã được sử dụng', 'error')
            return redirect(url_for('auth.register'))

        # Tạo user mới
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            department=department,
            position=position,
            role='user'  # Mặc định role là user
        )
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()

            # Gửi email xác nhận
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
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')

    departments = ['Phòng Nghiên cứu', 'Phòng Thí nghiệm', 'Phòng Quản lý']
    positions = ['Nghiên cứu viên', 'Kỹ thuật viên', 'Quản lý', 'Nhân viên']
    return render_template('auth/register.html', 
                         departments=departments,
                         positions=positions)

@auth.route('/confirm/<token>')
def confirm_email(token):
    user = User.verify_confirmation_token(token)
    if user is None:
        flash('Link xác nhận không hợp lệ hoặc đã hết hạn', 'error')
        return redirect(url_for('auth.login'))
    
    if user.is_active:
        flash('Tài khoản đã được xác nhận rồi', 'info')
    else:
        user.is_active = True
        db.session.commit()
        user.log_activity('email_confirm', 'Xác nhận email thành công')
        flash('Xác nhận tài khoản thành công!', 'success')
    
    return redirect(url_for('auth.login'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Tên đăng nhập hoặc mật khẩu không chính xác', 'danger')
            return redirect(url_for('auth.login'))
            
        if not user.is_active:
            flash('Tài khoản chưa được kích hoạt. Vui lòng kiểm tra email.', 'warning')
            return redirect(url_for('auth.login'))
            
        # Kiểm tra xác thực 2 lớp nếu được bật
        if user.otp_enabled:
            otp_code = request.form.get('otp_code')
            if not otp_code or not user.verify_otp(otp_code):
                flash('Mã xác thực không chính xác', 'danger')
                return render_template('auth/login.html', show_otp=True)
        
        login_user(user, remember=remember)
        user.last_login = db.func.now()
        user.log_activity('login')
        db.session.commit()
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('index'))
        
    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    current_user.log_activity('logout')
    logout_user()
    flash('Đã đăng xuất thành công', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html')

@auth.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.department = request.form.get('department')
        current_user.position = request.form.get('position')
        current_user.phone = request.form.get('phone')
        current_user.address = request.form.get('address')
        
        avatar_file = request.files.get('avatar')
        if avatar_file:
            # Xử lý upload avatar
            pass
        
        try:
            db.session.commit()
            current_user.log_activity('profile_update')
            flash('Cập nhật thông tin thành công', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
            
        return redirect(url_for('auth.profile'))
        
    departments = ['Phòng Nghiên cứu', 'Phòng Thí nghiệm', 'Phòng Quản lý']
    positions = ['Nghiên cứu viên', 'Kỹ thuật viên', 'Quản lý', 'Nhân viên']
    return render_template('auth/edit_profile.html',
                         departments=departments,
                         positions=positions)

@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(current_password):
            flash('Mật khẩu hiện tại không đúng', 'error')
            return redirect(url_for('auth.change_password'))

        if new_password != confirm_password:
            flash('Mật khẩu mới không khớp', 'error')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(new_password)
        db.session.commit()
        current_user.log_activity('password_change')
        flash('Đổi mật khẩu thành công', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/change_password.html')

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = user.generate_reset_token()
            # Gửi email với link reset password
            send_reset_password_email(user, token)
            flash('Hướng dẫn đặt lại mật khẩu đã được gửi đến email của bạn', 'info')
        else:
            flash('Không tìm thấy tài khoản với email này', 'danger')
            
        return redirect(url_for('auth.login'))
        
    return render_template('auth/forgot_password.html')

def send_reset_password_email(user, token):
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    msg = Message('Đặt lại mật khẩu',
                  recipients=[user.email])
    msg.body = f'''Để đặt lại mật khẩu, vui lòng truy cập link sau:
{reset_url}

Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.
'''
    mail.send(msg)

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_password_token=token).first()
    
    if not user or not user.verify_reset_token():
        flash('Link khôi phục mật khẩu không hợp lệ hoặc đã hết hạn', 'error')
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Mật khẩu không khớp', 'error')
            return redirect(url_for('auth.reset_password', token=token))
            
        user.set_password(password)
        user.clear_reset_token()
        user.log_activity('password_reset')
        flash('Đặt lại mật khẩu thành công', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html')

@auth.route('/activity-log')
@login_required
def activity_log():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    if current_user.role == 'admin':
        activities = UserActivity.query
    else:
        activities = UserActivity.query.filter_by(user_id=current_user.id)
        
    activities = activities.order_by(UserActivity.timestamp.desc()).paginate(
        page=page, per_page=per_page
    )
    
    return render_template('auth/activity_log.html', activities=activities)

@auth.route('/manage-users')
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    per_page = 20
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
        
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page
    )
    
    return render_template('auth/manage_users.html', users=users)

@auth.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.email = request.form.get('email')
        user.department = request.form.get('department')
        user.position = request.form.get('position')
        user.role = request.form.get('role')
        user.is_active = bool(request.form.get('is_active'))
        
        try:
            db.session.commit()
            current_user.log_activity('edit_user', f'Chỉnh sửa người dùng: {user.username}')
            flash('Cập nhật thông tin người dùng thành công', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
            
        return redirect(url_for('auth.manage_users'))
        
    departments = ['Phòng Nghiên cứu', 'Phòng Thí nghiệm', 'Phòng Quản lý']
    positions = ['Nghiên cứu viên', 'Kỹ thuật viên', 'Quản lý', 'Nhân viên']
    roles = ['admin', 'manager', 'researcher', 'user']
    
    return render_template('auth/edit_user.html',
                         user=user,
                         departments=departments,
                         positions=positions,
                         roles=roles)

@auth.route('/delete-user/<int:user_id>')
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Không thể xóa tài khoản của chính mình', 'error')
        return redirect(url_for('auth.manage_users'))
        
    try:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        current_user.log_activity('delete_user', f'Xóa người dùng: {username}')
        flash('Xóa người dùng thành công', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')
        
    return redirect(url_for('auth.manage_users')) 
