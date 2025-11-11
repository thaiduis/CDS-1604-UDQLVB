from __future__ import annotations

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CategoryBase(BaseModel):
	name: str
	description: Optional[str] = None
	color: Optional[str] = None


class CategoryCreate(CategoryBase):
	pass


class CategoryOut(CategoryBase):
	id: int
	created_at: datetime

	class Config:
		from_attributes = True


class FolderBase(BaseModel):
	name: str
	description: Optional[str] = None
	parent_id: Optional[int] = None
	color: Optional[str] = None


class FolderCreate(FolderBase):
	pass


class FolderOut(FolderBase):
	id: int
	created_at: datetime
	updated_at: datetime
	children: List["FolderOut"] = []

	class Config:
		from_attributes = True


class FolderUpdate(BaseModel):
	name: Optional[str] = None
	description: Optional[str] = None
	parent_id: Optional[int] = None
	color: Optional[str] = None


class DocumentBase(BaseModel):
	title: str
	tags: Optional[str] = None
	category_id: Optional[int] = None
	folder_id: Optional[int] = None


class DocumentCreate(DocumentBase):
	pass


class DocumentOut(DocumentBase):
	id: int
	filename: str
	mime_type: Optional[str] = None
	filesize: Optional[int] = None
	category: Optional[CategoryOut] = None
	folder: Optional[FolderOut] = None
	created_at: datetime
	updated_at: datetime

	class Config:
		from_attributes = True


class SearchQuery(BaseModel):
	q: Optional[str] = None
	tags: Optional[str] = None
	title: Optional[str] = None
	category_id: Optional[int] = None
	folder_id: Optional[int] = None
	page: int = 1
	limit: int = 10


class ShareLinkBase(BaseModel):
	expires_at: Optional[datetime] = None


class ShareLinkCreate(ShareLinkBase):
	pass


class ShareLinkOut(ShareLinkBase):
	id: int
	document_id: int
	token: str
	access_count: int
	created_at: datetime

	class Config:
		from_attributes = True
