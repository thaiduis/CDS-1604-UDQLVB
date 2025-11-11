"""
Module tự động phân loại văn bản dựa trên nội dung
"""
import re
from typing import Optional, Dict, List
from .database import SessionLocal
from .models import Category, Document


class DocumentClassifier:
    """Lớp phân loại văn bản tự động"""
    
    def __init__(self):
        self.keywords = {
            "Lập trình": [
                "lập trình", "programming", "code", "coding", "algorithm", "thuật toán",
                "data structure", "cấu trúc dữ liệu", "python", "java", "javascript", "c++",
                "c#", "php", "ruby", "go", "rust", "swift", "kotlin", "typescript",
                "function", "hàm", "class", "object", "oop", "recursion", "đệ quy",
                "sorting", "sắp xếp", "searching", "tìm kiếm", "binary tree", "cây nhị phân"
            ],
            "Web Development": [
                "web", "website", "frontend", "backend", "html", "css", "javascript",
                "react", "vue", "angular", "nodejs", "express", "django", "flask",
                "api", "rest", "graphql", "json", "xml", "http", "https", "ajax",
                "responsive", "mobile-first", "bootstrap", "tailwind", "sass", "less",
                "spa", "ssr", "seo", "performance", "optimization", "caching"
            ],
            "Mobile App": [
                "mobile", "app", "application", "ios", "android", "react native",
                "flutter", "xamarin", "ionic", "cordova", "phonegap", "swift",
                "kotlin", "java", "objective-c", "dart", "ui", "ux", "design",
                "navigation", "gesture", "touch", "push notification", "offline",
                "app store", "google play", "deployment", "testing"
            ],
            "Database": [
                "database", "db", "sql", "mysql", "postgresql", "oracle", "sqlite",
                "nosql", "mongodb", "redis", "cassandra", "elasticsearch", "neo4j",
                "table", "bảng", "index", "query", "select", "insert", "update",
                "delete", "join", "foreign key", "primary key", "normalization",
                "denormalization", "transaction", "acid", "replication", "sharding"
            ],
            "DevOps": [
                "devops", "ci", "cd", "continuous integration", "continuous deployment",
                "docker", "kubernetes", "jenkins", "gitlab", "github actions", "azure devops",
                "terraform", "ansible", "chef", "puppet", "monitoring", "logging",
                "prometheus", "grafana", "elk stack", "microservices", "container",
                "orchestration", "scaling", "load balancing", "deployment", "rollback"
            ],
            "AI/ML": [
                "ai", "artificial intelligence", "machine learning", "ml", "deep learning",
                "neural network", "tensorflow", "pytorch", "keras", "scikit-learn",
                "data science", "data analysis", "pandas", "numpy", "matplotlib",
                "supervised learning", "unsupervised learning", "reinforcement learning",
                "classification", "regression", "clustering", "nlp", "computer vision",
                "model", "training", "prediction", "accuracy", "precision", "recall"
            ],
            "Cybersecurity": [
                "security", "cybersecurity", "bảo mật", "an ninh mạng", "hacking",
                "penetration testing", "vulnerability", "exploit", "firewall", "antivirus",
                "encryption", "mã hóa", "ssl", "tls", "https", "authentication", "authorization",
                "oauth", "jwt", "token", "password", "mật khẩu", "phishing", "malware",
                "virus", "trojan", "backdoor", "ddos", "sql injection", "xss"
            ],
            "Cloud Computing": [
                "cloud", "aws", "amazon web services", "azure", "google cloud", "gcp",
                "ec2", "s3", "lambda", "rds", "dynamodb", "cloudfront", "route53",
                "vpc", "iam", "cloudformation", "elastic beanstalk", "auto scaling",
                "load balancer", "cdn", "serverless", "microservices", "containers",
                "kubernetes", "docker", "terraform", "infrastructure as code"
            ],
            "System Design": [
                "system design", "architecture", "kiến trúc", "microservices", "monolith",
                "distributed system", "scalability", "performance", "load balancing",
                "caching", "database design", "api design", "rest", "graphql", "soap",
                "message queue", "kafka", "rabbitmq", "event-driven", "cqs", "cqrs",
                "design pattern", "mvc", "mvp", "mvvm", "singleton", "factory", "observer"
            ]
        }
    
    def classify_document(self, title: str, content: str, tags: str = "") -> Optional[int]:
        """
        Phân loại văn bản dựa trên tiêu đề, nội dung và tags
        
        Args:
            title: Tiêu đề văn bản
            content: Nội dung văn bản
            tags: Tags của văn bản
            
        Returns:
            ID của danh mục phù hợp nhất, hoặc None nếu không tìm thấy
        """
        if not title and not content:
            return None
            
        # Chuẩn hóa văn bản
        text = f"{title or ''} {content or ''} {tags or ''}".lower()
        
        # Loại bỏ dấu tiếng Việt để tìm kiếm chính xác hơn
        text = self._normalize_vietnamese(text)
        
        scores = {}
        
        # Tính điểm cho từng danh mục
        for category_name, keywords in self.keywords.items():
            score = 0
            for keyword in keywords:
                keyword_norm = self._normalize_vietnamese(keyword)
                # Đếm số lần xuất hiện của từ khóa
                count = text.count(keyword_norm)
                if count > 0:
                    # Trọng số cao hơn nếu từ khóa xuất hiện trong tiêu đề
                    if title and keyword_norm in self._normalize_vietnamese(title.lower()):
                        score += count * 3
                    else:
                        score += count * 1
            
            if score > 0:
                scores[category_name] = score
        
        # Tìm danh mục có điểm cao nhất
        if scores:
            best_category = max(scores.items(), key=lambda x: x[1])
            # Chỉ trả về nếu điểm số đủ cao (ít nhất 2 điểm)
            if best_category[1] >= 2:
                return self._get_category_id_by_name(best_category[0])
        
        return None
    
    def _normalize_vietnamese(self, text: str) -> str:
        """Chuẩn hóa văn bản tiếng Việt bằng cách loại bỏ dấu"""
        import unicodedata
        
        # Loại bỏ dấu
        normalized = unicodedata.normalize('NFD', text)
        without_accents = ''.join(
            char for char in normalized 
            if unicodedata.category(char) != 'Mn'
        )
        
        # Loại bỏ ký tự đặc biệt và chuyển về chữ thường
        cleaned = re.sub(r'[^\w\s]', ' ', without_accents)
        return cleaned.lower()
    
    def _get_category_id_by_name(self, category_name: str) -> Optional[int]:
        """Lấy ID của danh mục theo tên"""
        db = SessionLocal()
        try:
            category = db.query(Category).filter(Category.name == category_name).first()
            return category.id if category else None
        finally:
            db.close()
    
    def suggest_category(self, title: str, content: str, tags: str = "") -> Dict[str, any]:
        """
        Gợi ý danh mục phù hợp với điểm số
        
        Returns:
            Dict chứa thông tin danh mục được gợi ý
        """
        if not title and not content:
            return {"category_id": None, "confidence": 0, "suggestions": []}
            
        text = f"{title or ''} {content or ''} {tags or ''}".lower()
        text = self._normalize_vietnamese(text)
        
        suggestions = []
        
        for category_name, keywords in self.keywords.items():
            score = 0
            matched_keywords = []
            
            for keyword in keywords:
                keyword_norm = self._normalize_vietnamese(keyword)
                count = text.count(keyword_norm)
                if count > 0:
                    matched_keywords.append(keyword)
                    if title and keyword_norm in self._normalize_vietnamese(title.lower()):
                        score += count * 3
                    else:
                        score += count * 1
            
            if score > 0:
                category_id = self._get_category_id_by_name(category_name)
                suggestions.append({
                    "category_id": category_id,
                    "category_name": category_name,
                    "score": score,
                    "matched_keywords": matched_keywords[:5]  # Chỉ lấy 5 từ khóa đầu
                })
        
        # Sắp xếp theo điểm số giảm dần
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        
        # Tính confidence (độ tin cậy)
        confidence = 0
        if suggestions:
            max_score = suggestions[0]["score"]
            if max_score >= 5:
                confidence = min(100, (max_score / 10) * 100)
            elif max_score >= 2:
                confidence = (max_score / 5) * 100
        
        return {
            "category_id": suggestions[0]["category_id"] if suggestions else None,
            "confidence": round(confidence, 1),
            "suggestions": suggestions[:3]  # Chỉ trả về top 3
        }


def auto_classify_document(doc_id: int) -> Optional[int]:
    """
    Tự động phân loại một tài liệu
    
    Args:
        doc_id: ID của tài liệu cần phân loại
        
    Returns:
        ID của danh mục được gán, hoặc None nếu không phân loại được
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return None
        
        classifier = DocumentClassifier()
        category_id = classifier.classify_document(
            doc.title or "",
            doc.content or "",
            doc.tags or ""
        )
        
        if category_id:
            doc.category_id = category_id
            db.commit()
            return category_id
        
        return None
        
    except Exception as e:
        print(f"Error in auto_classify_document: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_classification_suggestions(title: str, content: str, tags: str = "") -> Dict[str, any]:
    """
    Lấy gợi ý phân loại cho văn bản
    
    Args:
        title: Tiêu đề văn bản
        content: Nội dung văn bản
        tags: Tags của văn bản
        
    Returns:
        Dict chứa gợi ý phân loại
    """
    classifier = DocumentClassifier()
    return classifier.suggest_category(title, content, tags)
