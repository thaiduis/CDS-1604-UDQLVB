from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
import secrets
import string
from ..database import get_db
from ..models import Document, ShareLink
from ..schemas import ShareLinkCreate, ShareLinkOut

router = APIRouter(prefix="/api/share", tags=["share"])


def generate_share_token(length: int = 32) -> str:
    """Tạo token ngẫu nhiên cho share link"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@router.post("/{document_id}")
async def create_share_link(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Tạo share link cho tài liệu"""
    try:
        # Kiểm tra tài liệu có tồn tại không
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Tạo token mới
        token = generate_share_token()
        
        # Kiểm tra token có trùng lặp không (rất hiếm)
        while db.query(ShareLink).filter(ShareLink.token == token).first():
            token = generate_share_token()
        
        # Tạo share link
        share_link = ShareLink(
            document_id=document_id,
            token=token,
            expires_at=None
        )
        
        db.add(share_link)
        db.commit()
        db.refresh(share_link)
        
        return {
            "id": share_link.id,
            "document_id": share_link.document_id,
            "token": share_link.token,
            "expires_at": share_link.expires_at,
            "access_count": share_link.access_count,
            "created_at": share_link.created_at
        }
    except Exception as e:
        db.rollback()
        print(f"Error creating share link: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating share link: {str(e)}")


@router.get("/{token}")
async def access_shared_document(
    token: str,
    db: Session = Depends(get_db)
):
    """Truy cập tài liệu qua share link"""
    share_link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if not share_link:
        raise HTTPException(status_code=404, detail="Share link not found")
    
    # Kiểm tra hết hạn
    if share_link.expires_at and share_link.expires_at < datetime.now():
        raise HTTPException(status_code=410, detail="Share link has expired")
    
    # Tăng số lần truy cập
    share_link.access_count += 1
    db.commit()
    
    # Lấy thông tin tài liệu
    document = db.query(Document).filter(Document.id == share_link.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document": document,
        "share_info": {
            "access_count": share_link.access_count,
            "created_at": share_link.created_at,
            "expires_at": share_link.expires_at
        }
    }


@router.get("/{token}/download")
async def download_shared_document(
    token: str,
    db: Session = Depends(get_db)
):
    """Tải xuống tài liệu qua share link"""
    share_link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if not share_link:
        raise HTTPException(status_code=404, detail="Share link not found")
    
    # Kiểm tra hết hạn
    if share_link.expires_at and share_link.expires_at < datetime.now():
        raise HTTPException(status_code=410, detail="Share link has expired")
    
    # Tăng số lần truy cập
    share_link.access_count += 1
    db.commit()
    
    # Lấy thông tin tài liệu
    document = db.query(Document).filter(Document.id == share_link.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Trả về file download (sử dụng logic tương tự như documents router)
    import os
    from fastapi.responses import FileResponse
    import mimetypes
    
    filepath = os.path.join("uploads", document.filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    mime = document.mime_type or mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    return FileResponse(filepath, media_type=mime, filename=document.filename)


@router.delete("/{token}")
async def revoke_share_link(
    token: str,
    db: Session = Depends(get_db)
):
    """Thu hồi share link"""
    share_link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if not share_link:
        raise HTTPException(status_code=404, detail="Share link not found")
    
    db.delete(share_link)
    db.commit()
    
    return {"message": "Share link revoked successfully"}


@router.get("/document/{document_id}/links", response_model=List[ShareLinkOut])
async def get_document_share_links(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Lấy danh sách share links của tài liệu"""
    # Kiểm tra tài liệu có tồn tại không
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    share_links = db.query(ShareLink).filter(ShareLink.document_id == document_id).all()
    return share_links
