from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import func
import os
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

app = Flask(__name__)

# Cấu hình database
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

# Khởi tạo database và login manager
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='user')  # user, editor, admin

class Mau(db.Model):
    __tablename__ = 'mau'
    id = db.Column(db.Integer, primary_key=True)
    ma_mau = db.Column(db.String(50), unique=True, nullable=False)
    ten = db.Column(db.String(100), nullable=False)
    mo_ta = db.Column(db.Text)
    ngay_cay = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    trang_thai = db.Column(db.String(50))
    phong_id = db.Column(db.Integer, db.ForeignKey('phong.id'), nullable=False)
    nhat_ky = db.relationship('NhatKy', backref='mau', lazy=True)

class Phong(db.Model):
    __tablename__ = 'phong'
    id = db.Column(db.Integer, primary_key=True)
    ten = db.Column(db.String(100), nullable=False)
    nhiet_do = db.Column(db.Float)
    do_am = db.Column(db.Float)
    mau_list = db.relationship('Mau', backref='phong', lazy=True)

class NhatKy(db.Model):
    __tablename__ = 'nhat_ky'
    id = db.Column(db.Integer, primary_key=True)
    mau_id = db.Column(db.Integer, db.ForeignKey('mau.id'), nullable=False)
    ngay_ghi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    noi_dung = db.Column(db.Text, nullable=False)

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

# Route xuất Excel
@app.route('/xuat-excel')
@login_required
def xuat_excel():
    data = Mau.query.join(Phong).add_columns(Mau.ma_mau, Mau.ten, Mau.trang_thai, Mau.ngay_cay, Phong.ten.label('phong'))
    df = pd.DataFrame([{ 'Mã Mẫu': d.ma_mau, 'Tên': d.ten, 'Trạng Thái': d.trang_thai, 'Ngày Cấy': d.ngay_cay, 'Phòng': d.phong } for d in data])
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="bao_cao_mau.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Route biểu đồ năng suất
@app.route('/bieu-do-nang-suat')
@login_required
def bieu_do():
    counts = db.session.query(func.strftime('%Y-%m', Mau.ngay_cay), func.count(Mau.id)).group_by(func.strftime('%Y-%m', Mau.ngay_cay)).all()
    if not counts:
        flash("Không có dữ liệu để vẽ biểu đồ", 'warning')
        return redirect(url_for('index'))
    months, values = zip(*counts)
    plt.figure(figsize=(10,5))
    plt.bar(months, values)
    plt.title("Số lượng mẫu theo tháng")
    plt.xticks(rotation=45)
    plt.tight_layout()
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    return send_file(img, mimetype='image/png')

# Route chuyển giao diện tối
@app.route('/dark-mode')
def dark_mode():
    resp = redirect(url_for('index'))
    resp.set_cookie('theme', 'dark')
    return resp

# Route chuyển giao diện sáng
@app.route('/light-mode')
def light_mode():
    resp = redirect(url_for('index'))
    resp.set_cookie('theme', 'light')
    return resp

# Đăng nhập / đăng xuất
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Đăng nhập thành công!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Sai tài khoản hoặc mật khẩu', 'error')
    return render_template('login.html')

# Tạo admin mẫu
@app.route('/create-admin')
def create_admin():
    if User.query.filter_by(username='admin').first():
        return 'Admin đã tồn tại'
    hashed_password = generate_password_hash('123456')
    admin = User(username='admin', password=hashed_password, role='admin')
    db.session.add(admin)
    db.session.commit()
    return 'Tạo admin thành công!'

# Đăng xuất
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Đăng xuất thành công', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
