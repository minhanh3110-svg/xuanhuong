from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard route showing overview of system status"""
    # Get statistics for dashboard
    stats = {
        'total_samples': Mau.query.count(),
        'active_samples': Mau.query.filter_by(trang_thai='Đang phát triển').count(),
        'total_rooms': Phong.query.count()
    }
    
    # Get recent activities
    recent_activities = NhatKy.query.order_by(NhatKy.ngay_ghi.desc()).limit(10).all()
    
    # Get rooms with environmental alerts
    rooms_with_alerts = Phong.query.filter(
        ((Phong.nhiet_do > 30) | (Phong.nhiet_do < 15)) |
        ((Phong.do_am > 80) | (Phong.do_am < 40))
    ).all()
    
    return render_template('main/dashboard.html',
                         stats=stats,
                         recent_activities=recent_activities,
                         rooms_with_alerts=rooms_with_alerts)

// ... existing code ...
