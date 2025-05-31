from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from sqlalchemy import func

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

db = SQLAlchemy(app)

# Models
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

# Routes
@app.route('/')
def index():
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
        query = query.filter(Mau.ten.ilike(f'%{search}%'))
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
        Phong.ten.label('name'),
        func.count(Mau.id).label('count')
    ).outerjoin(Mau).group_by(Phong.id, Phong.ten).all()
    
    # Lấy danh sách mẫu có phân trang
    mau_pagination = query.order_by(Mau.ngay_cay.desc()).paginate(page=page, per_page=per_page)
    
    # Lấy danh sách phòng cho bộ lọc
    rooms = Phong.query.all()
    
    return render_template('index.html',
                         mau_pagination=mau_pagination,
                         stats=stats,
                         room_stats=room_stats,
                         rooms=rooms)

@app.route('/them-mau-moi', methods=['GET', 'POST'])
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
            mau_moi = Mau(
                ma_mau=ma_mau,
                ten=ten,
                mo_ta=mo_ta,
                phong_id=phong_id,
                trang_thai='Mới tạo'
            )
            db.session.add(mau_moi)
            db.session.commit()
            flash('Thêm mẫu mới thành công!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
            return redirect(url_for('them_mau_moi'))
    
    phong_list = Phong.query.all()
    return render_template('them_mau_moi.html', phong_list=phong_list)

@app.route('/chi-tiet-mau/<int:id>')
def chi_tiet_mau(id):
    mau = Mau.query.get_or_404(id)
    return render_template('chi_tiet_mau.html', mau=mau)

@app.route('/cap-nhat-mau/<int:id>', methods=['GET', 'POST'])
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
def xoa_mau(id):
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
def phong_moi_truong():
    phong_list = Phong.query.all()
    return render_template('phong_moi_truong.html', phong_list=phong_list)

@app.route('/them-phong-moi', methods=['GET', 'POST'])
def them_phong_moi():
    if request.method == 'POST':
        ten_phong = request.form.get('ten_phong')
        nhiet_do = request.form.get('nhiet_do')
        do_am = request.form.get('do_am')
        
        if not ten_phong:
            flash('Vui lòng nhập tên phòng', 'error')
            return redirect(url_for('them_phong_moi'))
        
        try:
            phong_moi = Phong(
                ten=ten_phong,
                nhiet_do=float(nhiet_do) if nhiet_do else None,
                do_am=float(do_am) if do_am else None
            )
            db.session.add(phong_moi)
            db.session.commit()
            flash('Thêm phòng mới thành công!', 'success')
            return redirect(url_for('phong_moi_truong'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
            return redirect(url_for('them_phong_moi'))
    
    return render_template('them_phong_moi.html')

@app.route('/them-nhat-ky/<int:mau_id>', methods=['POST'])
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
def cap_nhat_moi_truong(phong_id):
    phong = Phong.query.get_or_404(phong_id)
    data = request.get_json()
    
    try:
        phong.nhiet_do = data.get('nhiet_do')
        phong.do_am = data.get('do_am')
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True) 