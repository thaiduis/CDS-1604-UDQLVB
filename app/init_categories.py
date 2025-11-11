"""
Script để khởi tạo các danh mục phân loại văn bản
"""
from .database import SessionLocal
from .models import Category


def init_default_categories():
    """Khởi tạo các danh mục phân loại mặc định"""
    db = SessionLocal()
    try:
        # Kiểm tra xem đã có danh mục nào chưa
        if db.query(Category).count() > 0:
            print("Các danh mục đã tồn tại, bỏ qua khởi tạo")
            return

        # Danh sách các danh mục phân loại văn bản CNTT
        categories = [
            {
                "name": "Lập trình",
                "description": "Tài liệu về ngôn ngữ lập trình, code, thuật toán, data structures",
                "color": "#3498db"
            },
            {
                "name": "Web Development",
                "description": "Tài liệu về phát triển web, frontend, backend, frameworks",
                "color": "#e74c3c"
            },
            {
                "name": "Mobile App",
                "description": "Tài liệu về phát triển ứng dụng di động iOS, Android, React Native",
                "color": "#f39c12"
            },
            {
                "name": "Database",
                "description": "Tài liệu về cơ sở dữ liệu, SQL, NoSQL, MongoDB, PostgreSQL",
                "color": "#27ae60"
            },
            {
                "name": "DevOps",
                "description": "Tài liệu về DevOps, CI/CD, Docker, Kubernetes, deployment",
                "color": "#9b59b6"
            },
            {
                "name": "AI/ML",
                "description": "Tài liệu về trí tuệ nhân tạo, machine learning, deep learning",
                "color": "#34495e"
            },
            {
                "name": "Cybersecurity",
                "description": "Tài liệu về bảo mật, an ninh mạng, penetration testing",
                "color": "#e67e22"
            },
            {
                "name": "Cloud Computing",
                "description": "Tài liệu về điện toán đám mây, AWS, Azure, Google Cloud",
                "color": "#1abc9c"
            },
            {
                "name": "System Design",
                "description": "Tài liệu về thiết kế hệ thống, kiến trúc phần mềm, microservices",
                "color": "#16a085"
            },
            {
                "name": "Khác",
                "description": "Các tài liệu CNTT khác không thuộc danh mục trên",
                "color": "#95a5a6"
            }
        ]

        # Thêm các danh mục vào database
        for cat_data in categories:
            category = Category(**cat_data)
            db.add(category)
        
        db.commit()
        print(f"Đã khởi tạo {len(categories)} danh mục phân loại")
        
    except Exception as e:
        print(f"Lỗi khi khởi tạo danh mục: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_default_categories()
