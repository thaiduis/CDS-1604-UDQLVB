from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models import Folder, Document
from ..schemas import FolderCreate, FolderOut, FolderUpdate

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("/", response_model=List[FolderOut])
async def list_folders(
    parent_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Lấy danh sách thư mục"""
    query = db.query(Folder)
    
    if parent_id is None:
        # Lấy thư mục gốc (không có parent)
        query = query.filter(Folder.parent_id.is_(None))
    else:
        # Lấy thư mục con của parent_id
        query = query.filter(Folder.parent_id == parent_id)
    
    folders = query.order_by(Folder.name).all()
    return folders


@router.get("/tree", response_model=List[FolderOut])
async def get_folder_tree(db: Session = Depends(get_db)):
    """Lấy cây thư mục đầy đủ"""
    def build_tree(parent_id=None):
        folders = db.query(Folder).filter(Folder.parent_id == parent_id).order_by(Folder.name).all()
        result = []
        for folder in folders:
            folder_dict = {
                "id": folder.id,
                "name": folder.name,
                "description": folder.description,
                "parent_id": folder.parent_id,
                "color": folder.color,
                "created_at": folder.created_at,
                "updated_at": folder.updated_at,
                "children": build_tree(folder.id)
            }
            result.append(folder_dict)
        return result
    
    return build_tree()


@router.post("/", response_model=FolderOut)
async def create_folder(
    folder: FolderCreate,
    db: Session = Depends(get_db)
):
    """Tạo thư mục mới"""
    # Kiểm tra parent_id có tồn tại không
    if folder.parent_id:
        parent = db.query(Folder).filter(Folder.id == folder.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")
    
    # Kiểm tra tên thư mục trùng lặp trong cùng parent
    existing = db.query(Folder).filter(
        Folder.name == folder.name,
        Folder.parent_id == folder.parent_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Folder name already exists in this location")
    
    db_folder = Folder(**folder.dict())
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    return db_folder


@router.get("/{folder_id}", response_model=FolderOut)
async def get_folder(
    folder_id: int,
    db: Session = Depends(get_db)
):
    """Lấy thông tin thư mục"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.put("/{folder_id}", response_model=FolderOut)
async def update_folder(
    folder_id: int,
    folder_update: FolderUpdate,
    db: Session = Depends(get_db)
):
    """Cập nhật thư mục"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Kiểm tra parent_id có tồn tại không
    if folder_update.parent_id:
        parent = db.query(Folder).filter(Folder.id == folder_update.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        
        # Kiểm tra không tạo vòng lặp
        if folder_update.parent_id == folder_id:
            raise HTTPException(status_code=400, detail="Cannot set folder as its own parent")
    
    # Cập nhật các trường
    update_data = folder_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(folder, field, value)
    
    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db)
):
    """Xóa thư mục"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Kiểm tra có thư mục con không
    children = db.query(Folder).filter(Folder.parent_id == folder_id).count()
    if children > 0:
        raise HTTPException(status_code=400, detail="Cannot delete folder with subfolders")
    
    # Di chuyển tài liệu về thư mục gốc (parent_id = None)
    db.query(Document).filter(Document.folder_id == folder_id).update({"folder_id": None})
    
    db.delete(folder)
    db.commit()
    return {"message": "Folder deleted successfully"}


@router.get("/{folder_id}/documents")
async def get_folder_documents(
    folder_id: int,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Lấy tài liệu trong thư mục"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    offset = (page - 1) * limit
    documents = db.query(Document).filter(
        Document.folder_id == folder_id
    ).offset(offset).limit(limit).all()
    
    total = db.query(Document).filter(Document.folder_id == folder_id).count()
    
    return {
        "documents": documents,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }
