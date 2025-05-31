from app import db
from datetime import datetime

class NhatKy(db.Model):
    """Model lưu trữ nhật ký theo dõi mẫu"""
    id = db.Column(db.Integer, primary_key=True)
    mau_id = db.Column(db.Integer, db.ForeignKey('mau.id'), nullable=False)
    nguoi_ghi_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    thoi_gian = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    noi_dung = db.Column(db.Text, nullable=False)
    
    # Relationships
    nguoi_ghi = db.relationship('User', backref='nhat_ky', lazy=True)
    
    def __init__(self, **kwargs):
        super(NhatKy, self).__init__(**kwargs)
    
    def __repr__(self):
        return f'<NhatKy {self.mau_id} - {self.thoi_gian}>'
    
    def to_dict(self):
        """Chuyển đổi bản ghi thành dictionary"""
        return {
            'id': self.id,
            'mau_id': self.mau_id,
            'nguoi_ghi': self.nguoi_ghi.full_name,
            'thoi_gian': self.thoi_gian.strftime('%Y-%m-%d %H:%M:%S'),
            'noi_dung': self.noi_dung
        }
    
    @staticmethod
    def them_ban_ghi(mau_id, nguoi_ghi_id, noi_dung):
        """Thêm bản ghi mới"""
        ban_ghi = NhatKy(
            mau_id=mau_id,
            nguoi_ghi_id=nguoi_ghi_id,
            noi_dung=noi_dung
        )
        db.session.add(ban_ghi)
        db.session.commit()
        return ban_ghi
