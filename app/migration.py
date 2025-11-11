"""
Migration script để thêm cột category_id vào bảng documents
"""
from sqlalchemy import text
from .database import engine


def add_category_column():
    """Thêm cột category_id vào bảng documents"""
    try:
        with engine.connect() as conn:
            # Kiểm tra xem cột đã tồn tại chưa
            check_column = text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'documents' 
                AND COLUMN_NAME = 'category_id'
            """)
            
            result = conn.execute(check_column).scalar()
            
            if result == 0:
                # Thêm cột category_id
                alter_table = text("""
                    ALTER TABLE documents 
                    ADD COLUMN category_id INT NULL,
                    ADD INDEX idx_documents_category_id (category_id)
                """)
                
                conn.execute(alter_table)
                conn.commit()
                print("✅ Đã thêm cột category_id vào bảng documents")
            else:
                print("ℹ️ Cột category_id đã tồn tại trong bảng documents")
                
    except Exception as e:
        print(f"❌ Lỗi khi thêm cột category_id: {e}")
        raise


def add_foreign_key_constraint():
    """Thêm foreign key constraint cho category_id"""
    try:
        with engine.connect() as conn:
            # Kiểm tra xem constraint đã tồn tại chưa
            check_fk = text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'documents' 
                AND COLUMN_NAME = 'category_id'
                AND REFERENCED_TABLE_NAME = 'categories'
            """)
            
            result = conn.execute(check_fk).scalar()
            
            if result == 0:
                # Thêm foreign key constraint
                add_fk = text("""
                    ALTER TABLE documents 
                    ADD CONSTRAINT fk_documents_category_id 
                    FOREIGN KEY (category_id) REFERENCES categories(id) 
                    ON DELETE SET NULL
                """)
                
                conn.execute(add_fk)
                conn.commit()
                print("✅ Đã thêm foreign key constraint cho category_id")
            else:
                print("ℹ️ Foreign key constraint đã tồn tại")
                
    except Exception as e:
        print(f"❌ Lỗi khi thêm foreign key constraint: {e}")
        # Không raise exception vì constraint có thể không cần thiết


def run_migration():
    """Chạy migration để cập nhật database"""
    print("🔄 Bắt đầu migration database...")
    
    try:
        add_category_column()
        add_foreign_key_constraint()
        print("✅ Migration hoàn thành thành công!")
        
    except Exception as e:
        print(f"❌ Migration thất bại: {e}")
        raise


if __name__ == "__main__":
    run_migration()
