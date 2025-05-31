from app import app, db
from sqlalchemy import inspect

def has_table(table_name):
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()

with app.app_context():
    # Kiểm tra xem các bảng đã tồn tại chưa
    if not (has_table('mau') and has_table('phong') and has_table('nhat_ky')):
        # Chỉ tạo bảng nếu chưa tồn tại
        db.create_all()
        print("Đã khởi tạo database thành công!")
    else:
        print("Database đã tồn tại, không cần khởi tạo lại.") 