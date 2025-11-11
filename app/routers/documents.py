from __future__ import annotations

import os
import mimetypes
from typing import List, Optional, Dict, Any
import math
import re
import unicodedata
from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, BackgroundTasks
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Document, Category, Folder, ShareLink
from ..schemas import DocumentOut
from ..ocr import extract_text_from_pdf, extract_text_from_image, extract_text_from_word
from ..classifier import auto_classify_document, get_classification_suggestions
import asyncio
import json

router = APIRouter()

# Khởi tạo templates trong main và mount, ở đây chỉ lấy đường dẫn
from ..main import templates, upload_dir  # noqa: E402

ALLOWED_IMAGE = {"image/jpeg", "image/png"}
ALLOWED_PDF = {"application/pdf"}
ALLOWED_WORD = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword"  # .doc (legacy)
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# Advanced Search Functions
def strip_accents(text: str) -> str:
    """Remove Vietnamese diacritics for accent-insensitive comparison."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()

def fuzzy_match(query: str, text: str, threshold: float = 0.6) -> bool:
    """Fuzzy matching using sequence matcher"""
    if not query or not text:
        return False
    return SequenceMatcher(None, query.lower(), text.lower()).ratio() >= threshold

def parse_boolean_query(query: str) -> Dict[str, Any]:
    """Parse boolean search query with AND, OR, NOT operators"""
    query = query.strip()
    
    # Handle NOT operator
    not_terms = []
    if ' NOT ' in query.upper():
        parts = re.split(r'\s+NOT\s+', query, flags=re.IGNORECASE)
        if len(parts) == 2:
            query = parts[0].strip()
            not_terms = [term.strip() for term in parts[1].split() if term.strip()]
    
    # Handle OR operator
    or_terms = []
    if ' OR ' in query.upper():
        or_terms = [term.strip() for term in re.split(r'\s+OR\s+', query, flags=re.IGNORECASE) if term.strip()]
        query = ""
    else:
        # Handle AND operator (default)
        and_terms = [term.strip() for term in re.split(r'\s+AND\s+', query, flags=re.IGNORECASE) if term.strip()]
        if len(and_terms) > 1:
            query = ""
        else:
            and_terms = [query] if query else []
    
    return {
        'query': query,
        'and_terms': and_terms if 'and_terms' in locals() else [],
        'or_terms': or_terms,
        'not_terms': not_terms
    }

def parse_wildcard_query(query: str) -> str:
    """Convert wildcard query to SQL LIKE pattern"""
    if not query:
        return query
    
    # Escape SQL special characters except wildcards
    query = query.replace('\\', '\\\\')
    query = query.replace('%', '\\%')
    query = query.replace('_', '\\_')
    
    # Convert wildcards
    query = query.replace('*', '%')
    query = query.replace('?', '_')
    
    return f"%{query}%"

def calculate_relevance_score(query: str, title: str, content: str, tags: str = "") -> float:
    """Calculate relevance score for search results"""
    if not query:
        return 0.0
    
    query_lower = query.lower()
    title_lower = title.lower() if title else ""
    content_lower = content.lower() if content else ""
    tags_lower = tags.lower() if tags else ""
    
    score = 0.0
    
    # Exact match in title (highest weight)
    if query_lower in title_lower:
        score += 10.0
    
    # Exact match in content
    if query_lower in content_lower:
        score += 5.0
    
    # Exact match in tags
    if query_lower in tags_lower:
        score += 8.0
    
    # Fuzzy match in title
    if fuzzy_match(query, title, 0.7):
        score += 6.0
    
    # Fuzzy match in content
    if fuzzy_match(query, content, 0.7):
        score += 3.0
    
    # Word count bonus
    query_words = query_lower.split()
    title_words = title_lower.split()
    content_words = content_lower.split()
    
    for word in query_words:
        if word in title_words:
            score += 2.0
        if word in content_words:
            score += 1.0
    
    return score

def save_upload(file: UploadFile, dest_dir: str) -> str:
    """Save uploaded file with safe name handling"""
    os.makedirs(dest_dir, exist_ok=True)
    filename = file.filename or "uploaded"
    # tránh trùng tên
    base, ext = os.path.splitext(filename)
    counter = 1
    safe_name = filename
    while os.path.exists(os.path.join(dest_dir, safe_name)):
        safe_name = f"{base}_{counter}{ext}"
        counter += 1
    filepath = os.path.join(dest_dir, safe_name)
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    return safe_name


@router.get("/")
async def list_documents(
    request: Request,
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="Search in content"),
    title: Optional[str] = Query(None, description="Filter by title"),
    tags: Optional[str] = Query(None, description="Filter by tags"),
    category_id: Optional[str] = Query(None, description="Filter by category"),
    folder_id: Optional[str] = Query(None, description="Filter by folder"),
    type: Optional[str] = Query(None, description="Filter by document type (pdf/image)"),
    min_size: Optional[int] = Query(None, description="Minimum file size in MB"),
    max_size: Optional[int] = Query(None, description="Maximum file size in MB"),
    date_from: Optional[str] = Query(None, description="Date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Date to (YYYY-MM-DD)"),
    fuzzy: bool = Query(False, description="Enable fuzzy search"),
    wildcard: bool = Query(False, description="Enable wildcard search"),
    boolean: bool = Query(False, description="Enable boolean operators"),
    case_sensitive: bool = Query(False, description="Case sensitive search"),
    exact_match: bool = Query(False, description="Exact match search"),
    include_content: bool = Query(False, description="Search in file content"),
    sort_by: str = Query("relevance", description="Sort by: relevance, date, title, size"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(5, ge=1, le=5, description="Items per page - max 5"),
):
    """List documents with search and pagination"""
    try:
        # Base query
        base_query = db.query(Document)
        conditions: List[str] = []
        params = {}

        # Apply search filters with advanced features
        if q:
            if boolean:
                # Parse boolean query
                parsed = parse_boolean_query(q)
                if parsed['and_terms']:
                    and_conditions = []
                    for i, term in enumerate(parsed['and_terms']):
                        if wildcard:
                            term = parse_wildcard_query(term)
                        and_conditions.append(f"(title LIKE :and_term_{i} OR content LIKE :and_term_{i} OR tags LIKE :and_term_{i})")
                        params[f"and_term_{i}"] = f"%{term}%"
                    if and_conditions:
                        conditions.append(f"({' AND '.join(and_conditions)})")
                
                if parsed['or_terms']:
                    or_conditions = []
                    for i, term in enumerate(parsed['or_terms']):
                        if wildcard:
                            term = parse_wildcard_query(term)
                        or_conditions.append(f"(title LIKE :or_term_{i} OR content LIKE :or_term_{i} OR tags LIKE :or_term_{i})")
                        params[f"or_term_{i}"] = f"%{term}%"
                    if or_conditions:
                        conditions.append(f"({' OR '.join(or_conditions)})")
                
                if parsed['not_terms']:
                    for i, term in enumerate(parsed['not_terms']):
                        if wildcard:
                            term = parse_wildcard_query(term)
                        conditions.append(f"(title NOT LIKE :not_term_{i} AND content NOT LIKE :not_term_{i} AND tags NOT LIKE :not_term_{i})")
                        params[f"not_term_{i}"] = f"%{term}%"
            else:
                # Regular search
                if wildcard:
                    q = parse_wildcard_query(q)
                    conditions.append("(title LIKE :q OR content LIKE :q OR tags LIKE :q)")
                    params["q"] = q
                else:
                    # Accent-insensitive LIKE using Vietnamese collation if available
                    # Fallback will be handled later if collation is not supported
                    conditions.append(
                        "(title COLLATE utf8mb4_vi_0900_ai_ci LIKE :q OR content COLLATE utf8mb4_vi_0900_ai_ci LIKE :q OR tags COLLATE utf8mb4_vi_0900_ai_ci LIKE :q)"
                    )
                    params["q"] = f"%{q}%"
        
        if title:
            if wildcard:
                title = parse_wildcard_query(title)
            conditions.append("title LIKE :title")
            params["title"] = f"%{title}%"
        if tags:
            if wildcard:
                tags = parse_wildcard_query(tags)
            conditions.append("tags LIKE :tags")
            params["tags"] = f"%{tags}%"
        
        if category_id and category_id.strip() != "":
            try:
                category_id_int = int(category_id)
                conditions.append("category_id = :category_id")
                params["category_id"] = category_id_int
            except (ValueError, TypeError):
                # Bỏ qua nếu category_id không hợp lệ
                pass
        
        if folder_id and folder_id.strip() != "":
            try:
                folder_id_int = int(folder_id)
                conditions.append("folder_id = :folder_id")
                params["folder_id"] = folder_id_int
            except (ValueError, TypeError):
                # Bỏ qua nếu folder_id không hợp lệ
                pass
        
        if type:
            if type == 'pdf':
                conditions.append("mime_type LIKE :mime_type")
                params["mime_type"] = "application/pdf"
            elif type == 'image':
                conditions.append("mime_type LIKE :mime_type")
                params["mime_type"] = "image/%"
            elif type == 'document':
                conditions.append("mime_type IN (:mime_types)")
                params["mime_types"] = ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
        
        # Bộ lọc kích thước file
        if min_size is not None:
            conditions.append("filesize >= :min_size")
            params["min_size"] = min_size * 1024 * 1024  # Convert MB to bytes
        
        if max_size is not None:
            conditions.append("filesize <= :max_size")
            params["max_size"] = max_size * 1024 * 1024  # Convert MB to bytes
        
        # Bộ lọc ngày
        if date_from:
            try:
                from datetime import datetime
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
                conditions.append("DATE(created_at) >= :date_from")
                params["date_from"] = date_from_obj.date()
            except ValueError:
                pass
        
        if date_to:
            try:
                from datetime import datetime
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
                conditions.append("DATE(created_at) <= :date_to")
                params["date_to"] = date_to_obj.date()
            except ValueError:
                pass

        # Build query
        if conditions:
            where_sql = " AND ".join(conditions)
            # Count total first
            count_sql = f"SELECT COUNT(*) FROM documents WHERE {where_sql}"
            try:
                total = db.execute(text(count_sql), params).scalar()
            except Exception:
                # Fallback for servers without utf8mb4_vi_0900_ai_ci collation: do a broader fetch then filter in Python
                # Rebuild a simpler WHERE using default LIKE to reduce set, then post-filter by accent-insensitive match
                fallback_params = {**{k: v for k, v in params.items() if k not in ("q",)}, "q_plain": f"%{q}%"} if "q" in params else params
                fallback_where = where_sql.replace(
                    "title COLLATE utf8mb4_vi_0900_ai_ci LIKE :q",
                    "title LIKE :q_plain"
                ).replace(
                    "content COLLATE utf8mb4_vi_0900_ai_ci LIKE :q",
                    "content LIKE :q_plain"
                ).replace(
                    "tags COLLATE utf8mb4_vi_0900_ai_ci LIKE :q",
                    "tags LIKE :q_plain"
                )
                count_sql_fb = f"SELECT COUNT(*) FROM documents WHERE {fallback_where}"
                total = db.execute(text(count_sql_fb), fallback_params).scalar()
            
            # Determine sort order
            order_clause = "created_at DESC"
            if sort_by == "relevance" and q:
                # For relevance sorting, we'll do it in Python after fetching
                order_clause = "created_at DESC"
            elif sort_by == "title":
                order_clause = "title ASC"
            elif sort_by == "date":
                order_clause = "created_at DESC"
            elif sort_by == "size":
                order_clause = "filesize DESC"
            
            # Then get paginated results
            try:
                stmt = text(
                    f"SELECT * FROM documents WHERE {where_sql} "
                    f"ORDER BY {order_clause} LIMIT :limit OFFSET :offset"
                )
                params["limit"] = limit
                params["offset"] = (page - 1) * limit
                rows = db.execute(stmt, params).mappings().all()
                docs = [Document(**dict(r)) for r in rows]
            except Exception:
                # Fallback query without Vietnamese collation, then filter by accent-insensitive match in Python
                fallback_params = {**{k: v for k, v in params.items() if k not in ("q",)}, "q_plain": f"%{q}%"} if "q" in params else params
                fallback_where = where_sql.replace(
                    "title COLLATE utf8mb4_vi_0900_ai_ci LIKE :q",
                    "title LIKE :q_plain"
                ).replace(
                    "content COLLATE utf8mb4_vi_0900_ai_ci LIKE :q",
                    "content LIKE :q_plain"
                ).replace(
                    "tags COLLATE utf8mb4_vi_0900_ai_ci LIKE :q",
                    "tags LIKE :q_plain"
                )
                stmt_fb = text(
                    f"SELECT * FROM documents WHERE {fallback_where} "
                    f"ORDER BY {order_clause} LIMIT :limit OFFSET :offset"
                )
                fallback_params["limit"] = limit
                fallback_params["offset"] = (page - 1) * limit
                rows = db.execute(stmt_fb, fallback_params).mappings().all()
                docs_all = [Document(**dict(r)) for r in rows]
                # Post-filter accent-insensitive
                q_norm = strip_accents(q)
                filtered: List[Document] = []
                for doc in docs_all:
                    title_norm = strip_accents(doc.title or "")
                    content_norm = strip_accents(doc.content or "")
                    tags_norm = strip_accents(doc.tags or "")
                    if q_norm in title_norm or q_norm in content_norm or q_norm in tags_norm:
                        filtered.append(doc)
                docs = filtered
            
            # Apply relevance scoring and sorting if needed
            if sort_by == "relevance" and q and docs:
                for doc in docs:
                    doc.relevance_score = calculate_relevance_score(
                        q, doc.title or "", doc.content or "", doc.tags or ""
                    )
                docs.sort(key=lambda x: getattr(x, 'relevance_score', 0), reverse=True)
        else:
            # No search conditions - use ORM
            total = base_query.count()
            docs = (
                base_query.order_by(Document.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
                .all()
            )

        total_pages = math.ceil(total / limit)
        
        # Auto-redirect logic
        if total > 0:
            # If current page is beyond total pages, redirect to last page
            if page > total_pages:
                query_params = request.query_params
                new_params = query_params.copy()
                new_params["page"] = total_pages
                redirect_url = f"/documents/?{new_params}"
                return RedirectResponse(url=redirect_url)
            
            # If current page is empty but there are documents, redirect to page 1
            if not docs and page > 1:
                query_params = request.query_params
                new_params = query_params.copy()
                new_params["page"] = 1
                redirect_url = f"/documents/?{new_params}"
                return RedirectResponse(url=redirect_url)

        # Lấy danh sách các danh mục và thư mục để hiển thị trong dropdown
        categories = db.query(Category).order_by(Category.name).all()
        folders = db.query(Folder).order_by(Folder.name).all()
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "documents": docs,
                "categories": categories,
                "folders": folders,
                "q": q or "",
                "title": title or "",
                "tags": tags or "",
                "category_id": category_id if category_id and category_id.strip() != "" else "",
                "folder_id": folder_id if folder_id and folder_id.strip() != "" else "",
                "type": type or "",
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            },
        )
    except Exception as e:
        print(f"Error in list_documents: {e}")
        # Return empty page with error message
        categories = db.query(Category).order_by(Category.name).all()
        folders = db.query(Folder).order_by(Folder.name).all()
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "documents": [],
                "categories": categories,
                "folders": folders,
                "q": q or "",
                "title": title or "",
                "tags": tags or "",
                "category_id": "",  # Reset category_id nếu có lỗi
                "folder_id": "",  # Reset folder_id nếu có lỗi
                "type": type or "",
                "page": 1,
                "limit": limit,
                "total": 0,
                "total_pages": 0,
                "error": f"Database error: {str(e)}"
            },
        )


@router.get("/{doc_id}")
async def document_detail(
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None),
):
    """Get document details"""
    doc = db.get(Document, doc_id)
    if not doc:
        request.state.flash("Không tìm thấy tài liệu", "error")
        return RedirectResponse(url="/documents")
    return templates.TemplateResponse(
        "detail.html",
        {"request": request, "doc": doc, "q": q or ""}
    )


@router.put("/{doc_id}/content")
async def update_document_content(
    doc_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Update document text content"""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    try:
        new_content = payload.get("content", "")
        doc.content = new_content
        db.commit()
        return {"message": "Đã cập nhật nội dung"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi cập nhật nội dung: {str(e)}")


@router.get("/{doc_id}/download")
async def download_document(doc_id: int, request: Request, db: Session = Depends(get_db)):
    """Download document file"""
    doc = db.get(Document, doc_id)
    if not doc:
        request.state.flash("Không tìm thấy tài liệu", "error")
        return RedirectResponse(url="/documents")
    
    filepath = os.path.join(upload_dir, doc.filename)
    if not os.path.exists(filepath):
        request.state.flash("File không tồn tại", "error")
        return RedirectResponse(url="/documents")
    
    mime = doc.mime_type or mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    return FileResponse(filepath, media_type=mime, filename=doc.filename)


@router.post("/upload")
async def upload_document(
    request: Request,
    title: str = Form(...),
    tags: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    folder_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload new document"""
    # Validate file
    error = None
    if not file.content_type:
        error = "Thiếu content-type"
    elif file.content_type not in ALLOWED_IMAGE and file.content_type not in ALLOWED_PDF and file.content_type not in ALLOWED_WORD:
        error = "Định dạng không hỗ trợ. Chỉ hỗ trợ PDF, ảnh (JPEG/PNG) và Word (.docx/.doc)"
    else:
        file_contents = file.file.read()
        if len(file_contents) > MAX_FILE_SIZE:
            error = "File vượt quá 10MB"
        file.file.seek(0)

    if error:
        documents = db.query(Document).order_by(Document.created_at.desc()).limit(5).all()
        categories = db.query(Category).order_by(Category.name).all()
        total = db.query(Document).count()
        total_pages = 1
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "documents": documents,
                "categories": categories,
                "q": "",
                "title": "",
                "tags": "",
                "category_id": None,
                "type": "",
                "page": 1,
                "limit": 5,
                "total": total,
                "total_pages": total_pages,
                "error": error,
            },
        )

    # Reset file pointer
    try:
        saved_name = save_upload(file, upload_dir)
        filepath = os.path.join(upload_dir, saved_name)

        # Extract text content with fast mode for better speed
        content = ""
        try:
            if file.content_type in ALLOWED_PDF:
                content = extract_text_from_pdf(filepath)
            elif file.content_type in ALLOWED_IMAGE:
                # Prefer Vietnamese-only model when OCR image for better accuracy
                content = extract_text_from_image(filepath, lang="vie", fast_mode=True)
            elif file.content_type in ALLOWED_WORD:
                content = extract_text_from_word(filepath)
        except Exception as e:
            # Log error but continue
            print(f"Error extracting content: {e}")
            request.state.flash("Không thể trích xuất nội dung từ file, nhưng file đã được lưu", "warning")

        doc = Document(
            title=title,
            filename=saved_name,
            content=content,
            tags=tags,
            category_id=category_id,
            folder_id=folder_id,
            mime_type=file.content_type,
            filesize=os.path.getsize(filepath),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # Tự động phân loại nếu chưa có danh mục
        if not category_id and content:
            try:
                auto_category_id = auto_classify_document(doc.id)
                if auto_category_id:
                    doc.category_id = auto_category_id
                    db.commit()
                    print(f"Tự động phân loại tài liệu {doc.id} vào danh mục {auto_category_id}")
            except Exception as e:
                print(f"Lỗi khi tự động phân loại: {e}")
        
        request.state.flash("Tải lên tài liệu thành công", "success")
        return {"id": doc.id, "message": "Tải lên thành công"}

    except Exception as e:
        # Clean up file if saved
        if "saved_name" in locals():
            try:
                os.remove(os.path.join(upload_dir, saved_name))
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Lỗi khi tải lên: {str(e)}")


@router.get("/{document_id}/preview")
async def get_document_preview(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get document preview data"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Trả về thông tin tài liệu dưới dạng JSON
    return {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "content": document.content,
        "tags": document.tags,
        "mime_type": document.mime_type,
        "filesize": document.filesize,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "category": {
            "id": document.category.id,
            "name": document.category.name,
            "color": document.category.color
        } if document.category else None,
        "folder": {
            "id": document.folder.id,
            "name": document.folder.name,
            "color": document.folder.color
        } if document.folder else None
    }


@router.post("/{doc_id}/reprocess")
async def reprocess_document(
    doc_id: int, 
    request: Request, 
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Reprocess document OCR with progress tracking"""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    filepath = os.path.join(upload_dir, doc.filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File không tồn tại")
    
    # Start background OCR processing
    background_tasks.add_task(process_ocr_with_progress, doc_id, filepath, doc.mime_type, db)
    
    return {"message": "Đang xử lý OCR...", "status": "processing"}

async def process_ocr_with_progress(doc_id: int, filepath: str, mime_type: str, db: Session):
    """Background OCR processing with progress updates"""
    try:
        # Simulate progress updates
        progress = 0
        content = ""
        
        if mime_type in ALLOWED_PDF:
            # PDF processing with progress simulation
            progress = 10
            content = extract_text_from_pdf(filepath)
            progress = 90
        elif mime_type in ALLOWED_IMAGE:
            # Image processing
            progress = 20
            content = extract_text_from_image(filepath, fast_mode=True)
            progress = 80
        elif mime_type in ALLOWED_WORD:
            # Word processing
            progress = 30
            content = extract_text_from_word(filepath)
            progress = 70
        
        # Update document in database
        doc = db.get(Document, doc_id)
        if doc:
            doc.content = content
            db.commit()
            progress = 100
        
    except Exception as e:
        print(f"Error in background OCR processing: {e}")

@router.get("/{doc_id}/progress")
async def get_ocr_progress(doc_id: int, db: Session = Depends(get_db)):
    """Get OCR processing progress"""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    # Simple progress simulation - in real implementation, you'd use Redis or similar
    return {"progress": 100, "status": "completed", "content_length": len(doc.content or "")}

@router.delete("/{doc_id}")
async def delete_document(doc_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete document and its file"""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    # Delete related share links first
    share_links = db.query(ShareLink).filter(ShareLink.document_id == doc_id).all()
    for share_link in share_links:
        db.delete(share_link)
    
    # Delete file first
    filepath = os.path.join(upload_dir, doc.filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Error deleting file: {e}")
            request.state.flash("Không thể xóa file nhưng đã xóa thông tin tài liệu", "warning")
    
    # Then delete DB record
    db.delete(doc)
    db.commit()
    
    request.state.flash("Đã xóa tài liệu thành công", "success")
    return {"message": "Đã xóa tài liệu thành công"}

@router.get("/api/search/suggestions")
async def get_search_suggestions(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of suggestions"),
    db: Session = Depends(get_db)
):
    """Get search suggestions based on query"""
    try:
        if len(q) < 2:
            return {"suggestions": []}
        
        # Get suggestions from titles and tags
        suggestions = []
        q_norm = strip_accents(q)
        
        # Title suggestions
        # Try Vietnamese accent-insensitive collation first
        try:
            title_suggestions = db.execute(
                text("SELECT DISTINCT title FROM documents WHERE title COLLATE utf8mb4_vi_0900_ai_ci LIKE :q LIMIT :limit"),
                {"q": f"%{q}%", "limit": limit // 2}
            ).scalars().all()
        except Exception:
            # Fallback to default LIKE then filter in Python
            title_suggestions = db.execute(
                text("SELECT DISTINCT title FROM documents WHERE title LIKE :q LIMIT :limit"),
                {"q": f"%{q}%", "limit": limit // 2}
            ).scalars().all()
        
        for title in title_suggestions:
            if not title:
                continue
            title_norm = strip_accents(title)
            if q_norm in title_norm:
                suggestions.append({
                    "text": title,
                    "type": "title",
                    "highlight": title
                })
        
        # Tag suggestions
        try:
            tag_suggestions = db.execute(
                text("SELECT DISTINCT tags FROM documents WHERE tags COLLATE utf8mb4_vi_0900_ai_ci LIKE :q LIMIT :limit"),
                {"q": f"%{q}%", "limit": limit // 2}
            ).scalars().all()
        except Exception:
            tag_suggestions = db.execute(
                text("SELECT DISTINCT tags FROM documents WHERE tags LIKE :q LIMIT :limit"),
                {"q": f"%{q}%", "limit": limit // 2}
            ).scalars().all()
        
        for tags in tag_suggestions:
            if tags:
                for tag in tags.split(','):
                    tag = tag.strip()
                    if not tag:
                        continue
                    tag_norm = strip_accents(tag)
                    if q_norm in tag_norm:
                        suggestions.append({
                            "text": tag,
                            "type": "tag",
                            "highlight": tag
                        })
        
        # Remove duplicates and limit results
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion["text"] not in seen:
                seen.add(suggestion["text"])
                unique_suggestions.append(suggestion)
                if len(unique_suggestions) >= limit:
                    break
        
        return {"suggestions": unique_suggestions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting suggestions: {str(e)}")

@router.get("/api/search/history")
async def get_search_history(
    limit: int = Query(10, ge=1, le=50, description="Number of recent searches"),
    db: Session = Depends(get_db)
):
    """Get recent search history"""
    try:
        # This would typically be stored in a separate table
        # For now, return empty list
        return {"history": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting search history: {str(e)}")

@router.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get document statistics"""
    try:
        total_docs = db.query(Document).count()
        limit = 5  # Max 5 documents per page
        total_pages = math.ceil(total_docs / limit) if total_docs > 0 else 1
        
        return {
            "total": total_docs,
            "displayed": min(limit, total_docs),  # Max 5 displayed
            "pages": total_pages,
            "currentPage": 1,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@router.get("/api/storage/sizes")
async def get_storage_sizes(db: Session = Depends(get_db)):
    """Return total storage usage breakdown by type in bytes"""
    try:
        total_size = db.execute(text("SELECT COALESCE(SUM(filesize),0) FROM documents")).scalar() or 0
        pdf_size = db.execute(text("SELECT COALESCE(SUM(filesize),0) FROM documents WHERE mime_type = 'application/pdf'")) .scalar() or 0
        image_size = db.execute(text("SELECT COALESCE(SUM(filesize),0) FROM documents WHERE mime_type IN ('image/jpeg','image/png')")) .scalar() or 0
        # Word assumed when not pdf and not image
        word_size = db.execute(text("SELECT COALESCE(SUM(filesize),0) FROM documents WHERE mime_type NOT IN ('application/pdf','image/jpeg','image/png')")) .scalar() or 0
        return {
            "total_size": int(total_size),
            "pdf_size": int(pdf_size),
            "word_size": int(word_size),
            "image_size": int(image_size),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting storage sizes: {str(e)}")


@router.post("/api/classify/suggest")
async def suggest_classification(
    title: str = Form(...),
    content: str = Form(""),
    tags: str = Form("")
):
    """Lấy gợi ý phân loại cho văn bản"""
    try:
        suggestions = get_classification_suggestions(title, content, tags)
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting classification suggestions: {str(e)}")


@router.post("/{doc_id}/classify")
async def classify_document(
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Tự động phân loại một tài liệu"""
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    try:
        category_id = auto_classify_document(doc_id)
        if category_id:
            doc.category_id = category_id
            db.commit()
            return {"message": "Đã phân loại tài liệu thành công", "category_id": category_id}
        else:
            return {"message": "Không thể tự động phân loại tài liệu này"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi phân loại: {str(e)}")
