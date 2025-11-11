from sqlalchemy import text, inspect
from .database import engine, Base
from .models import Folder, Document

def run_folder_migration():
    """Migration để thêm bảng folders và cột folder_id vào documents"""
    with engine.connect() as connection:
        inspector = inspect(engine)
        
        # Kiểm tra xem bảng 'folders' đã tồn tại chưa
        if not inspector.has_table("folders"):
            print("Creating 'folders' table...")
            Folder.__table__.create(engine)
            print("'folders' table created.")
        else:
            print("'folders' table already exists.")

        # Kiểm tra xem cột 'folder_id' đã tồn tại trong bảng 'documents' chưa
        columns = inspector.get_columns("documents")
        column_names = [col['name'] for col in columns]

        if "folder_id" not in column_names:
            print("Adding 'folder_id' column to 'documents' table...")
            with connection.begin():
                connection.execute(text("ALTER TABLE documents ADD COLUMN folder_id INT NULL;"))
                connection.execute(text("ALTER TABLE documents ADD CONSTRAINT fk_folder_id FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL;"))
                connection.execute(text("CREATE INDEX ix_documents_folder_id ON documents (folder_id);"))
            print("'folder_id' column added to 'documents' table.")
        else:
            print("'folder_id' column already exists in 'documents' table.")
        
        connection.commit()
        print("Folder migration completed successfully!")

if __name__ == "__main__":
    run_folder_migration()
