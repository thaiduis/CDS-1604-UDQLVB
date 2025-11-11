-- =====================================================
-- SCHEMA DATABASE CHO HỆ THỐNG QUẢN LÝ TÀI LIỆU VỚI PHÂN LOẠI
-- =====================================================

-- Tạo database nếu chưa tồn tại
CREATE DATABASE IF NOT EXISTS docmgr 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE docmgr;

-- =====================================================
-- BẢNG CATEGORIES - DANH MỤC PHÂN LOẠI VĂN BẢN
-- =====================================================
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE COMMENT 'Tên danh mục',
    description TEXT COMMENT 'Mô tả danh mục',
    color VARCHAR(7) COMMENT 'Mã màu hex (ví dụ: #3498db)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Thời gian tạo',
    
    INDEX idx_categories_name (name),
    INDEX idx_categories_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
COMMENT='Bảng danh mục phân loại văn bản';

-- =====================================================
-- BẢNG DOCUMENTS - TÀI LIỆU
-- =====================================================
CREATE TABLE IF NOT EXISTS documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL COMMENT 'Tiêu đề tài liệu',
    filename VARCHAR(512) NOT NULL COMMENT 'Tên file gốc',
    content LONGTEXT COMMENT 'Nội dung văn bản (OCR)',
    tags VARCHAR(255) COMMENT 'Tags phân cách bằng dấu phẩy',
    category_id INT NULL COMMENT 'ID danh mục phân loại',
    mime_type VARCHAR(100) COMMENT 'Loại MIME của file',
    filesize INT COMMENT 'Kích thước file (bytes)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Thời gian tạo',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Thời gian cập nhật',
    
    INDEX idx_documents_title (title),
    INDEX idx_documents_tags (tags),
    INDEX idx_documents_category_id (category_id),
    INDEX idx_documents_mime_type (mime_type),
    INDEX idx_documents_created_at (created_at),
    INDEX idx_documents_updated_at (updated_at),
    
    -- Foreign key constraint
    CONSTRAINT fk_documents_category_id 
        FOREIGN KEY (category_id) 
        REFERENCES categories(id) 
        ON DELETE SET NULL 
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
COMMENT='Bảng tài liệu chính';

-- =====================================================
-- FULLTEXT INDEX CHO TÌM KIẾM NÂNG CAO
-- =====================================================
-- Thêm FULLTEXT index cho tìm kiếm trong title, content, tags
ALTER TABLE documents 
ADD FULLTEXT INDEX ft_title_content_tags (title, content, tags);

-- =====================================================
-- DỮ LIỆU MẪU CHO CÁC DANH MỤC CÔNG NGHỆ THÔNG TIN
-- =====================================================
INSERT INTO categories (name, description, color) VALUES
('Lập trình', 'Tài liệu về ngôn ngữ lập trình, code, thuật toán, data structures', '#3498db'),
('Web Development', 'Tài liệu về phát triển web, frontend, backend, frameworks', '#e74c3c'),
('Mobile App', 'Tài liệu về phát triển ứng dụng di động iOS, Android, React Native', '#f39c12'),
('Database', 'Tài liệu về cơ sở dữ liệu, SQL, NoSQL, MongoDB, PostgreSQL', '#27ae60'),
('DevOps', 'Tài liệu về DevOps, CI/CD, Docker, Kubernetes, deployment', '#9b59b6'),
('AI/ML', 'Tài liệu về trí tuệ nhân tạo, machine learning, deep learning', '#34495e'),
('Cybersecurity', 'Tài liệu về bảo mật, an ninh mạng, penetration testing', '#e67e22'),
('Cloud Computing', 'Tài liệu về điện toán đám mây, AWS, Azure, Google Cloud', '#1abc9c'),
('System Design', 'Tài liệu về thiết kế hệ thống, kiến trúc phần mềm, microservices', '#16a085'),
('Khác', 'Các tài liệu CNTT khác không thuộc danh mục trên', '#95a5a6')
ON DUPLICATE KEY UPDATE 
    description = VALUES(description),
    color = VALUES(color);

-- =====================================================
-- VIEWS CHO BÁO CÁO VÀ THỐNG KÊ
-- =====================================================

-- View thống kê tài liệu theo danh mục
CREATE OR REPLACE VIEW v_documents_by_category AS
SELECT 
    c.id as category_id,
    c.name as category_name,
    c.color as category_color,
    COUNT(d.id) as document_count,
    COALESCE(SUM(d.filesize), 0) as total_size_bytes,
    ROUND(COALESCE(SUM(d.filesize), 0) / 1024 / 1024, 2) as total_size_mb,
    MAX(d.created_at) as latest_document,
    MIN(d.created_at) as earliest_document
FROM categories c
LEFT JOIN documents d ON c.id = d.category_id
GROUP BY c.id, c.name, c.color
ORDER BY document_count DESC;

-- View thống kê tài liệu theo loại file
CREATE OR REPLACE VIEW v_documents_by_type AS
SELECT 
    CASE 
        WHEN mime_type LIKE 'application/pdf' THEN 'PDF'
        WHEN mime_type LIKE 'image/%' THEN 'Hình ảnh'
        WHEN mime_type LIKE '%word%' OR mime_type LIKE '%document%' THEN 'Word'
        ELSE 'Khác'
    END as file_type,
    COUNT(*) as document_count,
    COALESCE(SUM(filesize), 0) as total_size_bytes,
    ROUND(COALESCE(SUM(filesize), 0) / 1024 / 1024, 2) as total_size_mb
FROM documents
GROUP BY file_type
ORDER BY document_count DESC;

-- View tài liệu với thông tin danh mục đầy đủ
CREATE OR REPLACE VIEW v_documents_with_category AS
SELECT 
    d.*,
    c.name as category_name,
    c.color as category_color,
    c.description as category_description,
    CASE 
        WHEN d.mime_type LIKE 'application/pdf' THEN 'PDF'
        WHEN d.mime_type LIKE 'image/%' THEN 'Hình ảnh'
        WHEN d.mime_type LIKE '%word%' OR d.mime_type LIKE '%document%' THEN 'Word'
        ELSE 'Khác'
    END as file_type_display
FROM documents d
LEFT JOIN categories c ON d.category_id = c.id
ORDER BY d.created_at DESC;

-- =====================================================
-- STORED PROCEDURES CHO CÁC THAO TÁC THƯỜNG DÙNG
-- =====================================================

DELIMITER //

-- Procedure để tìm kiếm tài liệu nâng cao
CREATE PROCEDURE sp_search_documents(
    IN p_query VARCHAR(255),
    IN p_category_id INT,
    IN p_file_type VARCHAR(50),
    IN p_limit INT,
    IN p_offset INT
)
BEGIN
    DECLARE where_clause TEXT DEFAULT '';
    DECLARE sql_query TEXT;
    
    -- Xây dựng điều kiện WHERE
    IF p_query IS NOT NULL AND p_query != '' THEN
        SET where_clause = CONCAT(where_clause, ' AND MATCH(title, content, tags) AGAINST(? IN BOOLEAN MODE)');
    END IF;
    
    IF p_category_id IS NOT NULL THEN
        SET where_clause = CONCAT(where_clause, ' AND category_id = ?');
    END IF;
    
    IF p_file_type IS NOT NULL AND p_file_type != '' THEN
        CASE p_file_type
            WHEN 'pdf' THEN SET where_clause = CONCAT(where_clause, ' AND mime_type = "application/pdf"');
            WHEN 'image' THEN SET where_clause = CONCAT(where_clause, ' AND mime_type LIKE "image/%"');
            WHEN 'word' THEN SET where_clause = CONCAT(where_clause, ' AND (mime_type LIKE "%word%" OR mime_type LIKE "%document%")');
        END CASE;
    END IF;
    
    -- Xây dựng câu query
    SET sql_query = CONCAT('
        SELECT d.*, c.name as category_name, c.color as category_color
        FROM documents d
        LEFT JOIN categories c ON d.category_id = c.id
        WHERE 1=1', where_clause, '
        ORDER BY d.created_at DESC
        LIMIT ? OFFSET ?
    ');
    
    -- Thực thi query động
    SET @sql = sql_query;
    PREPARE stmt FROM @sql;
    
    IF p_query IS NOT NULL AND p_query != '' AND p_category_id IS NOT NULL THEN
        EXECUTE stmt USING p_query, p_category_id, p_limit, p_offset;
    ELSEIF p_query IS NOT NULL AND p_query != '' THEN
        EXECUTE stmt USING p_query, p_limit, p_offset;
    ELSEIF p_category_id IS NOT NULL THEN
        EXECUTE stmt USING p_category_id, p_limit, p_offset;
    ELSE
        EXECUTE stmt USING p_limit, p_offset;
    END IF;
    
    DEALLOCATE PREPARE stmt;
END //

-- Procedure để thống kê tổng quan
CREATE PROCEDURE sp_get_dashboard_stats()
BEGIN
    SELECT 
        (SELECT COUNT(*) FROM documents) as total_documents,
        (SELECT COUNT(*) FROM categories) as total_categories,
        (SELECT COALESCE(SUM(filesize), 0) FROM documents) as total_storage_bytes,
        (SELECT ROUND(COALESCE(SUM(filesize), 0) / 1024 / 1024, 2) FROM documents) as total_storage_mb,
        (SELECT COUNT(*) FROM documents WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)) as documents_last_30_days,
        (SELECT COUNT(*) FROM documents WHERE category_id IS NULL) as unclassified_documents;
END //

DELIMITER ;

-- =====================================================
-- TRIGGERS CHO AUDIT VÀ LOGGING
-- =====================================================

-- Trigger để log khi tạo tài liệu mới
DELIMITER //
CREATE TRIGGER tr_documents_after_insert
AFTER INSERT ON documents
FOR EACH ROW
BEGIN
    INSERT INTO document_logs (document_id, action, created_at)
    VALUES (NEW.id, 'CREATE', NOW());
END //

-- Trigger để log khi cập nhật tài liệu
CREATE TRIGGER tr_documents_after_update
AFTER UPDATE ON documents
FOR EACH ROW
BEGIN
    INSERT INTO document_logs (document_id, action, created_at)
    VALUES (NEW.id, 'UPDATE', NOW());
END //

DELIMITER ;

-- =====================================================
-- BẢNG LOGS (TÙY CHỌN)
-- =====================================================
CREATE TABLE IF NOT EXISTS document_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    action ENUM('CREATE', 'UPDATE', 'DELETE', 'VIEW', 'DOWNLOAD') NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_document_logs_document_id (document_id),
    INDEX idx_document_logs_action (action),
    INDEX idx_document_logs_created_at (created_at),
    
    CONSTRAINT fk_document_logs_document_id 
        FOREIGN KEY (document_id) 
        REFERENCES documents(id) 
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
COMMENT='Bảng log hoạt động tài liệu';

-- =====================================================
-- INDEXES BỔ SUNG CHO PERFORMANCE
-- =====================================================

-- Composite index cho tìm kiếm thường dùng
CREATE INDEX idx_documents_category_created ON documents (category_id, created_at DESC);
CREATE INDEX idx_documents_mime_created ON documents (mime_type, created_at DESC);

-- Index cho tìm kiếm theo tags
CREATE INDEX idx_documents_tags_search ON documents (tags(100));

-- =====================================================
-- GRANTS VÀ PERMISSIONS (TÙY CHỌN)
-- =====================================================

-- Tạo user cho ứng dụng (thay đổi password theo nhu cầu)
-- CREATE USER IF NOT EXISTS 'docmgr_user'@'localhost' IDENTIFIED BY 'StrongPass123!';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON docmgr.* TO 'docmgr_user'@'localhost';
-- FLUSH PRIVILEGES;

-- =====================================================
-- COMMENTS VÀ DOCUMENTATION
-- =====================================================

-- Schema này bao gồm:
-- 1. Bảng categories: Quản lý danh mục phân loại
-- 2. Bảng documents: Lưu trữ thông tin tài liệu
-- 3. Views: Cung cấp dữ liệu tổng hợp cho báo cáo
-- 4. Stored procedures: Các thao tác tìm kiếm và thống kê
-- 5. Triggers: Logging và audit trail
-- 6. Indexes: Tối ưu performance cho các truy vấn thường dùng

-- Để sử dụng schema này:
-- 1. Chạy file này trong MySQL để tạo database và tables
-- 2. Cập nhật connection string trong ứng dụng
-- 3. Chạy ứng dụng để test các tính năng

SELECT 'Schema database đã được tạo thành công!' as status;
