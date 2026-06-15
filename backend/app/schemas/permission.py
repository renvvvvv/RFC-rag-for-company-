from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel

class FileTypePermissionCreate(BaseModel):
    target_type: str = "group"  # user/group/role
    target_id: UUID
    file_type: str
    permissions: List[str] = ["READ"]

class DocumentPermissionCreate(BaseModel):
    target_type: str = "group"
    target_id: UUID
    doc_id: UUID
    permission: str  # NONE/READ/WRITE/ADMIN

class ExcelSheetPermission(BaseModel):
    access_level: str = "PARTIAL"  # FULL/PARTIAL/NONE
    allowed_columns: List[str] = []
    denied_columns: List[str] = []
    allowed_rows: Optional[tuple] = None
    row_filter: Optional[str] = None

class FieldPermissionCreate(BaseModel):
    target_type: str = "group"
    target_id: UUID
    doc_id: UUID
    file_type: str  # word/excel
    word_config: Optional[Dict[str, Any]] = None
    excel_config: Optional[Dict[str, ExcelSheetPermission]] = None

class TagPermissionCreate(BaseModel):
    target_type: str = "group"
    target_id: UUID
    allowed_tags: List[str] = []
    denied_tags: List[str] = []

class PermissionCheckResponse(BaseModel):
    doc_id: UUID
    permission: str  # NONE/READ/WRITE/ADMIN
    security_level: str
