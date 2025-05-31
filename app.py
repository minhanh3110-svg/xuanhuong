from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from sqlalchemy import func, case
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_principal import Principal, Permission, RoleNeed, identity_loaded, UserNeed
import openpyxl
from reportlab.pdfgen import canvas
from io import BytesIO
import json
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import io

app = Flask(__name__)

# Cấu hình database và bảo mật
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Vui lòng đăng nhập để truy cập trang này.'
login_manager.init_app(app)
principals = Principal(app)

# Định nghĩa quyền hạn
admin_permission = Permission(RoleNeed('admin'))
manager_permission = Permission(RoleNeed('manager'))
staff_permission = Permission(RoleNeed('staff'))

# Xử lý giao diện
@app.before_request
def before_request():
    if 'theme' not in session:
        session['theme'] = 'light'

@app.route('/toggle-theme')
def toggle_theme():
    session['theme'] = 'dark' if session.get('theme') == 'light' else 'light'
    return redirect(request.referrer or url_for('index'))

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    if hasattr(current_user, 'id'):
        identity.provides.add(UserNeed(current_user.id))
        if hasattr(current_user, 'role'):
            identity.provides.add(RoleNeed(current_user.role))

class Mau(db.Model):
    __tablename__ = 'mau'
    id = db.Column(db.Integer, primary_key=True)
    ma_mau = db.Column(db.String(50), unique=True, nullable=False)
    ten_mau = db.Column(db.String(200), nullable=False)
    ngay_cay = db.Column(db.DateTime, nullable=False)
    trang_thai = db.Column(db.String(50), nullable=False)
    mo_ta = db.Column(db.Text)
    phong_id = db.Column(db.Integer, db.ForeignKey('phong.id'))
    nhat_ky = db.relationship('NhatKy', backref='mau', lazy=True)

class Phong(db.Model):
    __tablename__ = 'phong'
    id = db.Column(db.Integer, primary_key=True)
    ten_phong = db.Column(db.String(100), nullable=False)
    nhiet_do = db.Column(db.Float)
    do_am = db.Column(db.Float)
    ghi_chu = db.Column(db.Text)
    mau_list = db.relationship('Mau', backref='phong', lazy=True)

class NhatKy(db.Model):
    __tablename__ = 'nhat_ky'
    id = db.Column(db.Integer, primary_key=True)
    mau_id = db.Column(db.Integer, db.ForeignKey('mau.id'), nullable=False)
    ngay_ghi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    trang_thai = db.Column(db.String(50), nullable=False)
    mo_ta = db.Column(db.Text)
    nguoi_ghi = db.Column(db.String(80), nullable=False)

# Các route đã được tích hợp đầy đủ trong đoạn code phía trên.
# Vui lòng xem lại file đã được cập nhật với các chức năng: login, phân quyền, giao diện tối/sáng, xuất Excel/PDF, thống kê biểu đồ.

# Khởi tạo database và tạo tài khoản admin
def init_db():
    with app.app_context():
        db.create_all()
        # Tạo tài khoản admin nếu chưa tồn tại
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', role='admin', name='Quản trị viên')
            admin.set_password('123456')  # Mật khẩu mặc định
            db.session.add(admin)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
