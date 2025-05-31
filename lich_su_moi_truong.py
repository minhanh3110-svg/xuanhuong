from app import db
from datetime import datetime

class LichSuMoiTruong(db.Model):
    """Model lưu trữ lịch sử thông số môi trường của phòng"""
    id = db.Column(db.Integer, primary_key=True)
    phong_id = db.Column(db.Integer, db.ForeignKey('phong.id'), nullable=False)
    thoi_gian = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Thông số môi trường
    nhiet_do = db.Column(db.Float, nullable=False)  # °C
    do_am = db.Column(db.Float, nullable=False)  # %
    anh_sang = db.Column(db.Float)  # lux
    co2 = db.Column(db.Float)  # ppm
    
    def __init__(self, **kwargs):
        super(LichSuMoiTruong, self).__init__(**kwargs)
    
    def __repr__(self):
        return f'<LichSuMoiTruong {self.phong_id} - {self.thoi_gian}>'
    
    def to_dict(self):
        """Chuyển đổi bản ghi thành dictionary"""
        return {
            'id': self.id,
            'phong_id': self.phong_id,
            'thoi_gian': self.thoi_gian.strftime('%Y-%m-%d %H:%M:%S'),
            'nhiet_do': self.nhiet_do,
            'do_am': self.do_am,
            'anh_sang': self.anh_sang,
            'co2': self.co2
        }
    
    @staticmethod
    def them_ban_ghi(phong_id, nhiet_do, do_am, anh_sang=None, co2=None):
        """Thêm bản ghi mới"""
        ban_ghi = LichSuMoiTruong(
            phong_id=phong_id,
            nhiet_do=nhiet_do,
            do_am=do_am,
            anh_sang=anh_sang,
            co2=co2
        )
        db.session.add(ban_ghi)
        db.session.commit()
        return ban_ghi
