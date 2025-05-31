# Hệ thống Quản lý Mẫu

Hệ thống quản lý mẫu và theo dõi môi trường phòng thí nghiệm được xây dựng bằng Flask.

## Tính năng

- Quản lý mẫu (thêm, sửa, xóa, tìm kiếm)
- Theo dõi trạng thái mẫu
- Ghi nhật ký theo dõi
- Quản lý phòng môi trường
- Theo dõi nhiệt độ và độ ẩm
- Xuất báo cáo (Excel, PDF)
- Thống kê và biểu đồ
- Hỗ trợ giao diện sáng/tối

## Yêu cầu

- Python 3.8+
- pip

## Cài đặt

1. Tạo môi trường ảo:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Cài đặt các gói phụ thuộc:
```bash
pip install -r requirements.txt
```

3. Thiết lập biến môi trường:
```bash
# Linux/Mac
export FLASK_APP=app.py
export FLASK_ENV=development
export SECRET_KEY=your-secret-key
export DATABASE_URL=sqlite:///database.db  # hoặc URL PostgreSQL

# Windows
set FLASK_APP=app.py
set FLASK_ENV=development
set SECRET_KEY=your-secret-key
set DATABASE_URL=sqlite:///database.db
```

4. Khởi tạo cơ sở dữ liệu:
```bash
flask shell
>>> from app import db
>>> db.create_all()
>>> exit()
```

5. Tạo tài khoản admin:
```bash
# Truy cập URL sau trong trình duyệt
http://localhost:5000/tao-admin
```

## Chạy ứng dụng

```bash
flask run
```

Truy cập ứng dụng tại: http://localhost:5000

## Đăng nhập

- Tài khoản mặc định: admin
- Mật khẩu mặc định: 123456

## Cấu trúc thư mục

```
flask_app/
├── app.py              # Ứng dụng Flask chính
├── requirements.txt    # Các gói phụ thuộc
├── static/            # Tài nguyên tĩnh
│   └── css/
│       └── style.css  # CSS tùy chỉnh
└── templates/         # Các template HTML
    ├── base.html
    ├── index.html
    ├── login.html
    ├── them_mau.html
    ├── sua_mau.html
    ├── them_nhat_ky.html
    ├── phong_moi_truong.html
    ├── them_phong.html
    └── sua_phong.html
```

## Bảo mật

- Sử dụng Flask-Login cho xác thực người dùng
- Mã hóa mật khẩu với Werkzeug
- Phân quyền với Flask-Principal
- CSRF protection tích hợp
- Hỗ trợ PostgreSQL cho môi trường production

## Hỗ trợ

Nếu bạn gặp vấn đề hoặc có câu hỏi, vui lòng tạo issue trong repository.
