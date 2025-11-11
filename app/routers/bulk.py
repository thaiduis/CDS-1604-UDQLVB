from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models import Document, Category, Folder, ShareLink

router = APIRouter(prefix="/api/bulk", tags=["bulk"])


@router.post("/move-to-folder")
async def bulk_move_to_folder(
    document_ids: List[int],
    folder_id: Optional[int],
    db: Session = Depends(get_db)
):
    """Di chuyển nhiều tài liệu vào thư mục"""
    try:
        # Kiểm tra folder_id có tồn tại không (nếu được cung cấp)
        if folder_id:
            folder = db.query(Folder).filter(Folder.id == folder_id).first()
            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")
        
        # Cập nhật tài liệu
        updated_count = db.query(Document).filter(
            Document.id.in_(document_ids)
        ).update(
            {"folder_id": folder_id},
            synchronize_session=False
        )
        
        db.commit()
        
        return {
            "message": f"Đã di chuyển {updated_count} tài liệu",
            "updated_count": updated_count
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error moving documents: {str(e)}")


@router.post("/assign-category")
async def bulk_assign_category(
    document_ids: List[int],
    category_id: int,
    db: Session = Depends(get_db)
):
    """Gán danh mục cho nhiều tài liệu"""
    try:
        # Kiểm tra category_id có tồn tại không
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        
        # Cập nhật tài liệu
        updated_count = db.query(Document).filter(
            Document.id.in_(document_ids)
        ).update(
            {"category_id": category_id},
            synchronize_session=False
        )
        
        db.commit()
        
        return {
            "message": f"Đã gán danh mục cho {updated_count} tài liệu",
            "updated_count": updated_count,
            "category_name": category.name
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error assigning category: {str(e)}")


@router.post("/add-tags")
async def bulk_add_tags(
    document_ids: List[int],
    tags: str,
    db: Session = Depends(get_db)
):
    """Thêm tags cho nhiều tài liệu"""
    try:
        updated_count = 0
        
        for doc_id in document_ids:
            document = db.query(Document).filter(Document.id == doc_id).first()
            if document:
                # Thêm tags mới vào tags hiện tại
                existing_tags = document.tags or ""
                if existing_tags:
                    new_tags = f"{existing_tags}, {tags}"
                else:
                    new_tags = tags
                
                document.tags = new_tags
                updated_count += 1
        
        db.commit()
        
        return {
            "message": f"Đã thêm tags cho {updated_count} tài liệu",
            "updated_count": updated_count,
            "tags_added": tags
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding tags: {str(e)}")


@router.delete("/delete")
async def bulk_delete_documents(
    document_ids: List[int],
    db: Session = Depends(get_db)
):
    """Xóa nhiều tài liệu"""
    try:
        # Lấy thông tin tài liệu trước khi xóa
        documents = db.query(Document).filter(Document.id.in_(document_ids)).all()
        document_titles = [doc.title for doc in documents]
        
        # Xóa các share links liên quan trước
        share_links = db.query(ShareLink).filter(ShareLink.document_id.in_(document_ids)).all()
        for share_link in share_links:
            db.delete(share_link)
        
        # Xóa tài liệu
        deleted_count = db.query(Document).filter(
            Document.id.in_(document_ids)
        ).delete(synchronize_session=False)
        
        db.commit()
        
        return {
            "message": f"Đã xóa {deleted_count} tài liệu",
            "deleted_count": deleted_count,
            "deleted_titles": document_titles
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting documents: {str(e)}")


@router.post("/export-selected")
async def bulk_export_selected(
    document_ids: List[int],
    format: str = "json",
    db: Session = Depends(get_db)
):
    """Xuất thông tin nhiều tài liệu"""
    try:
        documents = db.query(Document).filter(Document.id.in_(document_ids)).all()
        
        if format == "json":
            export_data = []
            for doc in documents:
                export_data.append({
                    "id": doc.id,
                    "title": doc.title,
                    "filename": doc.filename,
                    "tags": doc.tags,
                    "category": doc.category.name if doc.category else None,
                    "folder": doc.folder.name if doc.folder else None,
                    "mime_type": doc.mime_type,
                    "filesize": doc.filesize,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
                })
            
            return {
                "format": "json",
                "count": len(export_data),
                "data": export_data
            }
        
        elif format == "csv":
            # Tạo CSV data
            csv_lines = ["ID,Title,Filename,Tags,Category,Folder,MIME Type,File Size,Created At,Updated At"]
            for doc in documents:
                csv_lines.append(f"{doc.id},{doc.title},{doc.filename},{doc.tags or ''},{doc.category.name if doc.category else ''},{doc.folder.name if doc.folder else ''},{doc.mime_type or ''},{doc.filesize or ''},{doc.created_at},{doc.updated_at}")
            
            return {
                "format": "csv",
                "count": len(documents),
                "data": "\n".join(csv_lines)
            }
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting documents: {str(e)}")


@router.get("/selection-info")
async def get_selection_info(
    document_ids: List[int],
    db: Session = Depends(get_db)
):
    """Lấy thông tin về các tài liệu được chọn"""
    try:
        documents = db.query(Document).filter(Document.id.in_(document_ids)).all()
        
        # Thống kê
        total_size = sum(doc.filesize or 0 for doc in documents)
        categories = set(doc.category.name for doc in documents if doc.category)
        folders = set(doc.folder.name for doc in documents if doc.folder)
        mime_types = set(doc.mime_type for doc in documents if doc.mime_type)
        
        return {
            "count": len(documents),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "categories": list(categories),
            "folders": list(folders),
            "mime_types": list(mime_types),
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "filename": doc.filename,
                    "size": doc.filesize,
                    "category": doc.category.name if doc.category else None,
                    "folder": doc.folder.name if doc.folder else None
                } for doc in documents
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting selection info: {str(e)}")

