from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.user import User
from app.models.mau import Mau
from app.models.phong import Phong
from app import db
from datetime import datetime
from werkzeug.utils import secure_filename
import os

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('main/index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    # Thống kê tổng quan
    stats = {
        'total_samples': Mau.query.count(),
        'growing_samples': Mau.query.filter_by(trang_thai='Đang phát triển').count(),
        'needs_attention': Mau.query.filter_by(trang_thai='Cần chăm sóc').count(),
        'total_rooms': Phong.query.count()
    }
    
    # Lấy danh sách mẫu mới nhất
    latest_samples = Mau.query.order_by(Mau.ngay_cay.desc()).limit(5).all()
    
    # Lấy thông tin các phòng
    rooms = Phong.query.all()
    
    return render_template('main/dashboard.html',
                         stats=stats,
                         latest_samples=latest_samples,
                         rooms=rooms)

@bp.route('/profile')
@login_required
def profile():
    # Thống kê hoạt động của người dùng
    stats = {
        'managing_samples': Mau.query.filter_by(nguoi_tao_id=current_user.id).count(),
        'total_logs': current_user.nhat_ky.count(),
        'success_rate': calculate_success_rate(current_user.id)
    }
    
    # Cài đặt thông báo
    notifications = {
        'email_alerts': current_user.email_alerts,
        'browser_notifications': current_user.browser_notifications
    }
    
    return render_template('main/profile.html',
                         stats=stats,
                         notifications=notifications)

@bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    if request.method == 'POST':
        try:
            current_user.full_name = request.form.get('full_name')
            current_user.phone = request.form.get('phone')
            current_user.department = request.form.get('department')
            current_user.address = request.form.get('address')
            
            # Xử lý upload avatar
            if 'avatar' in request.files:
                file = request.files['avatar']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    current_user.avatar_url = url_for('static', filename=f'uploads/{filename}')
            
            db.session.commit()
            flash('Cập nhật thông tin thành công!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
            
    return redirect(url_for('main.profile'))

@bp.route('/profile/notifications', methods=['POST'])
@login_required
def update_notifications():
    if request.method == 'POST':
        try:
            current_user.email_alerts = 'email_alerts' in request.form
            current_user.browser_notifications = 'browser_notifications' in request.form
            db.session.commit()
            flash('Cập nhật cài đặt thông báo thành công!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
            
    return redirect(url_for('main.profile'))

def calculate_success_rate(user_id):
    total_samples = Mau.query.filter_by(nguoi_tao_id=user_id).count()
    if total_samples == 0:
        return 0
        
    successful_samples = Mau.query.filter_by(
        nguoi_tao_id=user_id,
        trang_thai='Thành công'
    ).count()
    
    return round((successful_samples / total_samples) * 100)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
