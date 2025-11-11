from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import Dict, Any
from ..database import get_db
from ..models import Document, Category, Folder, ShareLink

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard_analytics(
    request: Request,
    db: Session = Depends(get_db)
):
    """Lấy thống kê tổng quan cho dashboard"""
    try:
        # Tổng số tài liệu
        total_documents = db.query(Document).count()
        
        # Tổng số danh mục
        total_categories = db.query(Category).count()
        
        # Tổng số thư mục
        total_folders = db.query(Folder).count()
        
        # Tổng số share links
        total_share_links = db.query(ShareLink).count()
        
        # Tài liệu theo danh mục
        documents_by_category = db.query(
            Category.name,
            Category.color,
            func.count(Document.id).label('count')
        ).outerjoin(Document).group_by(Category.id, Category.name, Category.color).all()
        
        # Tài liệu theo thư mục
        documents_by_folder = db.query(
            Folder.name,
            Folder.color,
            func.count(Document.id).label('count')
        ).outerjoin(Document).group_by(Folder.id, Folder.name, Folder.color).all()
        
        # Tài liệu theo loại file
        documents_by_type = db.query(
            func.substring(Document.mime_type, 1, func.locate('/', Document.mime_type) - 1).label('type'),
            func.count(Document.id).label('count')
        ).filter(Document.mime_type.isnot(None)).group_by('type').all()
        
        # Tài liệu mới nhất (7 ngày qua)
        recent_documents = db.query(Document).filter(
            Document.created_at >= func.date_sub(func.now(), text('INTERVAL 7 DAY'))
        ).count()
        
        # Tài liệu được chia sẻ nhiều nhất
        most_shared_documents = db.query(
            Document.id,
            Document.title,
            func.count(ShareLink.id).label('share_count')
        ).join(ShareLink).group_by(Document.id, Document.title).order_by(
            func.count(ShareLink.id).desc()
        ).limit(5).all()
        
        # Thống kê dung lượng
        total_size = db.query(func.sum(Document.filesize)).scalar() or 0
        avg_size = db.query(func.avg(Document.filesize)).scalar() or 0
        
        # Tài liệu theo tháng (12 tháng qua)
        monthly_stats = db.query(
            func.year(Document.created_at).label('year'),
            func.month(Document.created_at).label('month'),
            func.count(Document.id).label('count')
        ).filter(
            Document.created_at >= func.date_sub(func.now(), text('INTERVAL 12 MONTH'))
        ).group_by('year', 'month').order_by('year', 'month').all()
        
        return {
            "overview": {
                "total_documents": total_documents,
                "total_categories": total_categories,
                "total_folders": total_folders,
                "total_share_links": total_share_links,
                "recent_documents": recent_documents,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2) if total_size else 0,
                "avg_size_bytes": round(avg_size) if avg_size else 0,
                "avg_size_mb": round(avg_size / (1024 * 1024), 2) if avg_size else 0
            },
            "by_category": [
                {
                    "name": item.name,
                    "color": item.color,
                    "count": item.count
                } for item in documents_by_category
            ],
            "by_folder": [
                {
                    "name": item.name,
                    "color": item.color,
                    "count": item.count
                } for item in documents_by_folder
            ],
            "by_type": [
                {
                    "type": item.type,
                    "count": item.count
                } for item in documents_by_type
            ],
            "most_shared": [
                {
                    "id": item.id,
                    "title": item.title,
                    "share_count": item.share_count
                } for item in most_shared_documents
            ],
            "monthly_stats": [
                {
                    "year": item.year,
                    "month": item.month,
                    "count": item.count
                } for item in monthly_stats
            ]
        }
    except Exception as e:
        print(f"Error getting analytics: {e}")
        return {"error": str(e)}


@router.get("/search-stats")
async def get_search_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """Lấy thống kê tìm kiếm"""
    try:
        # Tài liệu có nội dung tìm kiếm được
        searchable_documents = db.query(Document).filter(
            Document.content.isnot(None),
            Document.content != ''
        ).count()
        
        # Tài liệu có tags
        tagged_documents = db.query(Document).filter(
            Document.tags.isnot(None),
            Document.tags != ''
        ).count()
        
        # Tài liệu được phân loại
        categorized_documents = db.query(Document).filter(
            Document.category_id.isnot(None)
        ).count()
        
        # Tài liệu trong thư mục
        folderized_documents = db.query(Document).filter(
            Document.folder_id.isnot(None)
        ).count()
        
        return {
            "searchable_documents": searchable_documents,
            "tagged_documents": tagged_documents,
            "categorized_documents": categorized_documents,
            "folderized_documents": folderized_documents,
            "search_coverage": {
                "content": round((searchable_documents / max(total_documents, 1)) * 100, 2),
                "tags": round((tagged_documents / max(total_documents, 1)) * 100, 2),
                "categories": round((categorized_documents / max(total_documents, 1)) * 100, 2),
                "folders": round((folderized_documents / max(total_documents, 1)) * 100, 2)
            }
        }
    except Exception as e:
        print(f"Error getting search stats: {e}")
        return {"error": str(e)}


@router.get("/storage-stats")
async def get_storage_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """Lấy thống kê lưu trữ"""
    try:
        # Thống kê dung lượng theo loại file
        size_by_type = db.query(
            func.substring(Document.mime_type, 1, func.locate('/', Document.mime_type) - 1).label('type'),
            func.sum(Document.filesize).label('total_size'),
            func.count(Document.id).label('count'),
            func.avg(Document.filesize).label('avg_size')
        ).filter(
            Document.filesize.isnot(None)
        ).group_by('type').all()
        
        # Tài liệu lớn nhất
        largest_documents = db.query(
            Document.id,
            Document.title,
            Document.filesize,
            Document.mime_type
        ).filter(
            Document.filesize.isnot(None)
        ).order_by(Document.filesize.desc()).limit(10).all()
        
        # Phân bố kích thước
        size_distribution = db.query(
            func.case(
                (Document.filesize < 1024 * 1024, 'Small (< 1MB)'),
                (Document.filesize < 10 * 1024 * 1024, 'Medium (1-10MB)'),
                (Document.filesize < 100 * 1024 * 1024, 'Large (10-100MB)'),
                else_='Very Large (> 100MB)'
            ).label('size_category'),
            func.count(Document.id).label('count')
        ).filter(
            Document.filesize.isnot(None)
        ).group_by('size_category').all()
        
        return {
            "by_type": [
                {
                    "type": item.type,
                    "total_size": item.total_size,
                    "count": item.count,
                    "avg_size": round(item.avg_size) if item.avg_size else 0
                } for item in size_by_type
            ],
            "largest_documents": [
                {
                    "id": item.id,
                    "title": item.title,
                    "size": item.filesize,
                    "type": item.mime_type
                } for item in largest_documents
            ],
            "size_distribution": [
                {
                    "category": item.size_category,
                    "count": item.count
                } for item in size_distribution
            ]
        }
    except Exception as e:
        print(f"Error getting storage stats: {e}")
        return {"error": str(e)}

