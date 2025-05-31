from app import db
from datetime import datetime

class Phong(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ten = db.Column(db.String(100), nullable=False)
    mo_ta = db.Column(db.Text)
    nhiet_do = db.Column(db.Float)
    do_am = db.Column(db.Float)
    anh_sang = db.Column(db.Float)  # Cường độ ánh sáng (lux)
    co2 = db.Column(db.Float)  # Nồng độ CO2 (ppm)
    trang_thai = db.Column(db.String(50), default='Hoạt động')
    last_update = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    mau_list = db.relationship('Mau', backref='phong', lazy=True)
    lich_su = db.relationship('LichSuMoiTruong', backref='phong', lazy=True)
    
    def cap_nhat_moi_truong(self, nhiet_do=None, do_am=None, anh_sang=None, co2=None):
        """Cập nhật thông số môi trường và lưu lịch sử"""
        if nhiet_do is not None:
            self.nhiet_do = nhiet_do
        if do_am is not None:
            self.do_am = do_am
        if anh_sang is not None:
            self.anh_sang = anh_sang
        if co2 is not None:
            self.co2 = co2
            
        self.last_update = datetime.utcnow()
        
        # Lưu lịch sử
        lich_su = LichSuMoiTruong(
            phong_id=self.id,
            nhiet_do=self.nhiet_do,
            do_am=self.do_am,
            anh_sang=self.anh_sang,
            co2=self.co2
        )
        db.session.add(lich_su)
        db.session.commit()
        
        # Kiểm tra và tạo cảnh báo nếu cần
        self.kiem_tra_canh_bao()
    
    def kiem_tra_canh_bao(self):
        """Kiểm tra và tạo cảnh báo nếu các thông số vượt ngưỡng"""
        from app.models.user import User, Notification
        
        canh_bao = []
        
        # Kiểm tra nhiệt độ (20-30°C)
        if self.nhiet_do < 20 or self.nhiet_do > 30:
            canh_bao.append(f'Nhiệt độ: {self.nhiet_do}°C')
            
        # Kiểm tra độ ẩm (60-80%)
        if self.do_am < 60 or self.do_am > 80:
            canh_bao.append(f'Độ ẩm: {self.do_am}%')
            
        # Kiểm tra ánh sáng (1000-10000 lux)
        if self.anh_sang and (self.anh_sang < 1000 or self.anh_sang > 10000):
            canh_bao.append(f'Ánh sáng: {self.anh_sang} lux')
            
        # Kiểm tra CO2 (350-1000 ppm)
        if self.co2 and (self.co2 < 350 or self.co2 > 1000):
            canh_bao.append(f'CO2: {self.co2} ppm')
        
        if canh_bao:
            # Tạo thông báo cho admin
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                notification = Notification(
                    user_id=admin.id,
                    title=f'Cảnh báo môi trường - {self.ten}',
                    message='Các thông số vượt ngưỡng:\n' + '\n'.join(canh_bao),
                    type='warning'
                )
                db.session.add(notification)
            
            db.session.commit()

class LichSuMoiTruong(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phong_id = db.Column(db.Integer, db.ForeignKey('phong.id'), nullable=False)
    thoi_gian = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    nhiet_do = db.Column(db.Float)
    do_am = db.Column(db.Float)
    anh_sang = db.Column(db.Float)
    co2 = db.Column(db.Float)
    
    def __repr__(self):
        return f'<LichSuMoiTruong {self.phong.ten} - {self.thoi_gian}>'
