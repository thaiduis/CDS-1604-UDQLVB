from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Category(Base):
	__tablename__ = "categories"

	id = Column(Integer, primary_key=True, index=True)
	name = Column(String(100), nullable=False, unique=True, index=True)
	description = Column(Text, nullable=True)
	color = Column(String(7), nullable=True)  # Hex color code
	created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Folder(Base):
	__tablename__ = "folders"

	id = Column(Integer, primary_key=True, index=True)
	name = Column(String(255), nullable=False, index=True)
	description = Column(Text, nullable=True)
	parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True, index=True)
	color = Column(String(7), nullable=True)  # Hex color code
	created_at = Column(DateTime, server_default=func.now(), nullable=False)
	updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

	# Self-referential relationship for folder hierarchy
	parent = relationship("Folder", remote_side=[id], backref="children")


class Document(Base):
	__tablename__ = "documents"

	id = Column(Integer, primary_key=True, index=True)
	title = Column(String(255), nullable=False, index=True)
	filename = Column(String(512), nullable=False)
	content = Column(Text, nullable=True)
	tags = Column(String(255), nullable=True, index=True)
	category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
	folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True, index=True)
	mime_type = Column(String(100), nullable=True)
	filesize = Column(Integer, nullable=True)
	created_at = Column(DateTime, server_default=func.now(), nullable=False)
	updated_at = Column(
		DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
	)

	# Relationships
	category = relationship("Category", backref="documents")
	folder = relationship("Folder", backref="documents")


class ShareLink(Base):
	__tablename__ = "share_links"

	id = Column(Integer, primary_key=True, index=True)
	document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
	token = Column(String(255), unique=True, nullable=False, index=True)
	expires_at = Column(DateTime, nullable=True)
	access_count = Column(Integer, default=0, nullable=False)
	created_at = Column(DateTime, server_default=func.now(), nullable=False)

	# Relationship
	document = relationship("Document", backref="share_links")
