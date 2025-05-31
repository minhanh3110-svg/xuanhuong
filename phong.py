from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.phong import Phong, LichSuMoiTruong
from app import db
from datetime import datetime, timedelta

bp = Blueprint('phong', __name__)

@bp.route('/phong-moi-truong')
@login_required
def phong_moi_truong():
    phong_list = Phong.query.all()
    return render_template('phong/phong_moi_truong.html', phong_list=phong_list)

@bp.route('/them-phong-moi', methods=['GET', 'POST'])
@login_required
def them_phong_moi():
    if request.method == 'POST':
        try:
            phong = Phong(
                ten=request.form.get('ten'),
                mo_ta=request.form.get('mo_ta'),
                nhiet_do=float(request.form.get('nhiet_do')) if request.form.get('nhiet_do') else None,
                do_am=float(request.form.get('do_am')) if request.form.get('do_am') else None,
                anh_sang=float(request.form.get('anh_sang')) if request.form.get('anh_sang') else None,
                co2=float(request.form.get('co2')) if request.form.get('co2') else None
            )
            db.session.add(phong)
            db.session.commit()
            flash('Thêm phòng mới thành công!', 'success')
            return redirect(url_for('phong.phong_moi_truong'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
    
    return render_template('phong/them_phong.html')

@bp.route('/chi-tiet-phong/<int:id>')
@login_required
def chi_tiet_phong(id):
    phong = Phong.query.get_or_404(id)
    
    # Lấy lịch sử môi trường trong 24h qua
    now = datetime.utcnow()
    lich_su = LichSuMoiTruong.query.filter(
        LichSuMoiTruong.phong_id == id,
        LichSuMoiTruong.thoi_gian >= now - timedelta(days=1)
    ).order_by(LichSuMoiTruong.thoi_gian.desc()).all()
    
    # Chuẩn bị dữ liệu cho biểu đồ
    labels = []
    nhiet_do_data = []
    do_am_data = []
    anh_sang_data = []
    co2_data = []
    
    for ls in reversed(lich_su):
        labels.append(ls.thoi_gian.strftime('%H:%M'))
        nhiet_do_data.append(ls.nhiet_do)
        do_am_data.append(ls.do_am)
        anh_sang_data.append(ls.anh_sang)
        co2_data.append(ls.co2)
    
    chart_data = {
        'labels': labels,
        'nhiet_do': nhiet_do_data,
        'do_am': do_am_data,
        'anh_sang': anh_sang_data,
        'co2': co2_data
    }
    
    return render_template('phong/chi_tiet_phong.html', 
                         phong=phong, 
                         chart_data=chart_data)

@bp.route('/cap-nhat-phong/<int:id>', methods=['GET', 'POST'])
@login_required
def cap_nhat_phong(id):
    phong = Phong.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            phong.ten = request.form.get('ten')
            phong.mo_ta = request.form.get('mo_ta')
            phong.trang_thai = request.form.get('trang_thai')
            
            # Cập nhật thông số môi trường
            nhiet_do = request.form.get('nhiet_do')
            do_am = request.form.get('do_am')
            anh_sang = request.form.get('anh_sang')
            co2 = request.form.get('co2')
            
            phong.cap_nhat_moi_truong(
                nhiet_do=float(nhiet_do) if nhiet_do else None,
                do_am=float(do_am) if do_am else None,
                anh_sang=float(anh_sang) if anh_sang else None,
                co2=float(co2) if co2 else None
            )
            
            flash('Cập nhật phòng thành công!', 'success')
            return redirect(url_for('phong.chi_tiet_phong', id=phong.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
    
    return render_template('phong/cap_nhat_phong.html', phong=phong)

@bp.route('/xoa-phong/<int:id>')
@login_required
def xoa_phong(id):
    if current_user.role != 'admin':
        flash('Bạn không có quyền xóa phòng!', 'error')
        return redirect(url_for('phong.phong_moi_truong'))
    
    phong = Phong.query.get_or_404(id)
    
    # Kiểm tra xem phòng có đang chứa mẫu không
    if phong.mau_list:
        flash('Không thể xóa phòng đang chứa mẫu!', 'error')
        return redirect(url_for('phong.chi_tiet_phong', id=id))
    
    try:
        db.session.delete(phong)
        db.session.commit()
        flash('Xóa phòng thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')
    
    return redirect(url_for('phong.phong_moi_truong'))

@bp.route('/api/cap-nhat-moi-truong/<int:id>', methods=['POST'])
@login_required
def cap_nhat_moi_truong(id):
    """API để cập nhật thông số môi trường từ thiết bị"""
    if not request.is_json:
        return jsonify({'error': 'Yêu cầu phải là JSON'}), 400
    
    phong = Phong.query.get_or_404(id)
    data = request.get_json()
    
    try:
        nhiet_do = data.get('nhiet_do')
        do_am = data.get('do_am')
        anh_sang = data.get('anh_sang')
        co2 = data.get('co2')
        
        if nhiet_do is None or do_am is None:
            return jsonify({
                'error': 'Thiếu thông số nhiệt độ hoặc độ ẩm'
            }), 400
        
        # Validate ranges
        if not (-50 <= float(nhiet_do) <= 100):
            return jsonify({
                'error': 'Nhiệt độ không hợp lệ'
            }), 400
        
        if not (0 <= float(do_am) <= 100):
            return jsonify({
                'error': 'Độ ẩm không hợp lệ'
            }), 400
        
        if anh_sang is not None and not (0 <= float(anh_sang) <= 100000):
            return jsonify({
                'error': 'Cường độ ánh sáng không hợp lệ'
            }), 400
        
        if co2 is not None and not (0 <= float(co2) <= 5000):
            return jsonify({
                'error': 'Nồng độ CO2 không hợp lệ'
            }), 400
        
        phong.cap_nhat_moi_truong(
            nhiet_do=float(nhiet_do),
            do_am=float(do_am),
            anh_sang=float(anh_sang) if anh_sang is not None else None,
            co2=float(co2) if co2 is not None else None
        )
        
        return jsonify({
            'message': 'Cập nhật thành công',
            'data': {
                'nhiet_do': phong.nhiet_do,
                'do_am': phong.do_am,
                'anh_sang': phong.anh_sang,
                'co2': phong.co2,
                'last_update': phong.last_update.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except ValueError:
        return jsonify({
            'error': 'Giá trị không hợp lệ'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Lỗi hệ thống: {str(e)}'
        }), 500

@bp.route('/api/lich-su-moi-truong/<int:id>')
@login_required
def lich_su_moi_truong(id):
    """API để lấy lịch sử môi trường"""
    try:
        # Lấy thông số thời gian từ query string
        days = request.args.get('days', 1, type=int)
        if days > 30:  # Giới hạn tối đa 30 ngày
            days = 30
        
        now = datetime.utcnow()
        lich_su = LichSuMoiTruong.query.filter(
            LichSuMoiTruong.phong_id == id,
            LichSuMoiTruong.thoi_gian >= now - timedelta(days=days)
        ).order_by(LichSuMoiTruong.thoi_gian.asc()).all()
        
        data = [{
            'thoi_gian': ls.thoi_gian.strftime('%Y-%m-%d %H:%M:%S'),
            'nhiet_do': ls.nhiet_do,
            'do_am': ls.do_am,
            'anh_sang': ls.anh_sang,
            'co2': ls.co2
        } for ls in lich_su]
        
        return jsonify(data)
    except Exception as e:
        return jsonify({
            'error': f'Lỗi hệ thống: {str(e)}'
        }), 500
