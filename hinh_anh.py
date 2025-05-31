from app import db
from datetime import datetime

class HinhAnh(db.Model):
    """Model lưu trữ hình ảnh của mẫu"""
    id = db.Column(db.Integer, primary_key=True)
    mau_id = db.Column(db.Integer, db.ForeignKey('mau.id'), nullable=False)
    nguoi_chup_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    thoi_gian = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    url = db.Column(db.String(255), nullable=False)
    mo_ta = db.Column(db.Text)
    
    # Relationships
    nguoi_chup = db.relationship('User', backref='hinh_anh', lazy=True)
    
    def __init__(self, **kwargs):
        super(HinhAnh, self).__init__(**kwargs)
    
    def __repr__(self):
        return f'<HinhAnh {self.mau_id} - {self.thoi_gian}>'
    
    def to_dict(self):
        """Chuyển đổi bản ghi thành dictionary"""
        return {
            'id': self.id,
            'mau_id': self.mau_id,
            'nguoi_chup': self.nguoi_chup.full_name,
            'thoi_gian': self.thoi_gian.strftime('%Y-%m-%d %H:%M:%S'),
            'url': self.url,
            'mo_ta': self.mo_ta
        }
    
    @staticmethod
    def them_hinh_anh(mau_id, nguoi_chup_id, url, mo_ta=None):
        """Thêm hình ảnh mới"""
        hinh_anh = HinhAnh(
            mau_id=mau_id,
            nguoi_chup_id=nguoi_chup_id,
            url=url,
            mo_ta=mo_ta
        )
        db.session.add(hinh_anh)
        db.session.commit()
        return hinh_anh
