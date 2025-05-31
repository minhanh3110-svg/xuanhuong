from app import app, db, User
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        # Tạo tất cả các bảng
        db.create_all()
        
        # Kiểm tra xem đã có admin chưa
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # Tạo tài khoản admin mặc định
            admin = User(
                username='admin',
                email='admin@example.com',
                full_name='Administrator',
                password_hash=generate_password_hash('admin123'),
                role='admin',
                is_active=True,
                department='Phòng Quản lý',
                position='Quản trị viên'
            )
            db.session.add(admin)
            db.session.commit()
            print('Đã tạo tài khoản admin mặc định')
        
        print('Khởi tạo database thành công!')

if __name__ == '__main__':
    init_db() 