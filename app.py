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

# Bộ lọc template
@app.template_filter('status_color')
def status_color(status):
    colors = {
        'Mới tạo': 'success',
        'Đang phát triển': 'primary',
        'Đã hoàn thành': 'warning',
        'Thất bại': 'danger'
    }
    return colors.get(status, 'secondary')

# Routes
@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
        
    page = request.args.get('page', 1, type=int)
    per_page = 9
    
    # Lấy các tham số tìm kiếm
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    room = request.args.get('room', '')
    
    # Query cơ bản
    query = Mau.query
    
    # Áp dụng các bộ lọc
    if search:
        query = query.filter(Mau.ten_mau.ilike(f'%{search}%'))
    if status:
        query = query.filter(Mau.trang_thai == status)
    if room:
        query = query.filter(Mau.phong_id == room)
    
    # Lấy thống kê
    stats = {
        'new_count': Mau.query.filter_by(trang_thai='Mới tạo').count(),
        'developing_count': Mau.query.filter_by(trang_thai='Đang phát triển').count(),
        'completed_count': Mau.query.filter_by(trang_thai='Đã hoàn thành').count(),
        'failed_count': Mau.query.filter_by(trang_thai='Thất bại').count()
    }
    
    # Lấy thống kê theo phòng
    room_stats = db.session.query(
        Phong.ten_phong.label('name'),
        func.count(Mau.id).label('count')
    ).outerjoin(Mau).group_by(Phong.id, Phong.ten_phong).all()
    
    room_stats = [{'name': r.name, 'count': r.count} for r in room_stats]
    
    mau_pagination = query.order_by(Mau.ngay_cay.desc()).paginate(page=page, per_page=per_page)
    rooms = Phong.query.all()
    
    return render_template('index.html',
                         mau_pagination=mau_pagination,
                         stats=stats,
                         room_stats=room_stats,
                         rooms=rooms,
                         theme=session.get('theme', 'light'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Vui lòng nhập đầy đủ thông tin đăng nhập', 'error')
            return redirect(url_for('login'))
            
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            flash('Đăng nhập thành công!', 'success')
            return redirect(next_page or url_for('index'))
            
        flash('Sai tên đăng nhập hoặc mật khẩu', 'error')
    return render_template('login.html', theme=session.get('theme', 'light'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Đã đăng xuất thành công', 'success')
    return redirect(url_for('login'))

@app.route('/mau/them', methods=['GET', 'POST'])
@login_required
def them_mau():
    if request.method == 'POST':
        try:
            mau_moi = Mau(
                ma_mau=request.form['ma_mau'],
                ten_mau=request.form['ten_mau'],
                ngay_cay=datetime.strptime(request.form['ngay_cay'], '%Y-%m-%d'),
                trang_thai=request.form['trang_thai'],
                mo_ta=request.form['mo_ta'],
                phong_id=request.form['phong_id']
            )
            db.session.add(mau_moi)
            db.session.commit()
            flash('Thêm mẫu thành công', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi thêm mẫu: {str(e)}', 'error')
            
    phong_list = Phong.query.all()
    return render_template('them_mau.html', phong_list=phong_list, theme=session.get('theme', 'light'))

@app.route('/mau/<int:id>/sua', methods=['GET', 'POST'])
@login_required
def sua_mau(id):
    mau = Mau.query.get_or_404(id)
    if request.method == 'POST':
        try:
            mau.ma_mau = request.form['ma_mau']
            mau.ten_mau = request.form['ten_mau']
            mau.ngay_cay = datetime.strptime(request.form['ngay_cay'], '%Y-%m-%d')
            mau.trang_thai = request.form['trang_thai']
            mau.mo_ta = request.form['mo_ta']
            mau.phong_id = request.form['phong_id']
            db.session.commit()
            flash('Cập nhật mẫu thành công', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi cập nhật mẫu: {str(e)}', 'error')
            
    phong_list = Phong.query.all()
    return render_template('sua_mau.html', mau=mau, phong_list=phong_list, theme=session.get('theme', 'light'))

@app.route('/mau/<int:id>/xoa')
@login_required
def xoa_mau(id):
    mau = Mau.query.get_or_404(id)
    try:
        db.session.delete(mau)
        db.session.commit()
        flash('Xóa mẫu thành công', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Lỗi khi xóa mẫu: {str(e)}', 'error')
    return redirect(url_for('index'))

@app.route('/nhat-ky/them/<int:mau_id>', methods=['GET', 'POST'])
@login_required
def them_nhat_ky(mau_id):
    if request.method == 'POST':
        try:
            nhat_ky_moi = NhatKy(
                mau_id=mau_id,
                trang_thai=request.form['trang_thai'],
                mo_ta=request.form['mo_ta'],
                nguoi_ghi=current_user.username
            )
            db.session.add(nhat_ky_moi)
            db.session.commit()
            flash('Thêm nhật ký thành công', 'success')
            return redirect(url_for('xem_mau', id=mau_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi thêm nhật ký: {str(e)}', 'error')
            
    return render_template('them_nhat_ky.html', mau_id=mau_id, theme=session.get('theme', 'light'))

@app.route('/api/cap-nhat-moi-truong/<int:phong_id>', methods=['POST'])
def cap_nhat_moi_truong(phong_id):
    phong = Phong.query.get_or_404(phong_id)
    data = request.get_json()
    
    try:
        phong.nhiet_do = data.get('nhiet_do')
        phong.do_am = data.get('do_am')
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Cập nhật thành công'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Lỗi: {str(e)}'})

@app.route('/bao-cao/excel')
@login_required
def xuat_excel():
    mau_list = Mau.query.all()
    data = []
    for mau in mau_list:
        data.append({
            'Mã mẫu': mau.ma_mau,
            'Tên mẫu': mau.ten_mau,
            'Ngày cấy': mau.ngay_cay.strftime('%d/%m/%Y'),
            'Trạng thái': mau.trang_thai,
            'Phòng': Phong.query.get(mau.phong_id).ten_phong if mau.phong_id else ''
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='bao_cao_mau.xlsx'
    )

@app.route('/bao-cao/pdf')
@login_required
def xuat_pdf():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="Báo cáo mẫu nuôi cấy")
    elements = []
    
    mau_list = Mau.query.all()
    data = [['Mã mẫu', 'Tên mẫu', 'Ngày cấy', 'Trạng thái', 'Phòng']]
    for mau in mau_list:
        data.append([
            mau.ma_mau,
            mau.ten_mau,
            mau.ngay_cay.strftime('%d/%m/%Y'),
            mau.trang_thai,
            Phong.query.get(mau.phong_id).ten_phong if mau.phong_id else ''
        ])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='bao_cao_mau.pdf'
    )

@app.route('/api/thong-ke-trang-thai')
@login_required
def api_thong_ke_trang_thai():
    stats = {
        'labels': ['Mới tạo', 'Đang phát triển', 'Đã hoàn thành', 'Thất bại'],
        'data': [
            Mau.query.filter_by(trang_thai='Mới tạo').count(),
            Mau.query.filter_by(trang_thai='Đang phát triển').count(),
            Mau.query.filter_by(trang_thai='Đã hoàn thành').count(),
            Mau.query.filter_by(trang_thai='Thất bại').count()
        ]
    }
    return jsonify(stats)

@app.route('/api/thong-ke-nang-suat')
@login_required
def api_thong_ke_nang_suat():
    # Thống kê tỷ lệ thành công theo tháng
    success_rates = db.session.query(
        func.date_trunc('month', Mau.ngay_cay).label('month'),
        func.count(Mau.id).label('total'),
        func.sum(case([(Mau.trang_thai == 'Đã hoàn thành', 1)], else_=0)).label('success')
    ).group_by('month').order_by('month').all()
    
    stats = {
        'labels': [r.month.strftime('%m/%Y') for r in success_rates],
        'data': [round((r.success / r.total * 100), 2) if r.total > 0 else 0 for r in success_rates]
    }
    return jsonify(stats)
@app.route('/mau/<int:id>')
@login_required
def xem_mau(id):
    mau = Mau.query.get_or_404(id)
    nhat_ky_list = NhatKy.query.filter_by(mau_id=id).order_by(NhatKy.ngay_ghi.desc()).all()
    return render_template('xem_mau.html', mau=mau, nhat_ky_list=nhat_ky_list, theme=session.get('theme', 'light'))

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
