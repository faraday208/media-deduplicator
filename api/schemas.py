"""
Pydantic Schemas for API request/response models
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class HashAlgorithm(str, Enum):
    """Perceptual hash algorithms"""
    AVERAGE = "average_hash"
    PHASH = "phash"
    DHASH = "dhash"


class TaskStatus(str, Enum):
    """Background task status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Request Models
# ============================================================================

class ScanRequest(BaseModel):
    """Request to scan for duplicate images"""
    directory: str = Field(..., description="Directory path to scan")
    recursive: bool = Field(default=True, description="Scan subdirectories")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "directory": "/home/user/images",
                    "recursive": True
                }
            ]
        }
    }


class SimilarScanRequest(BaseModel):
    """Request to scan for similar images"""
    directory: str = Field(..., description="Directory path to scan")
    threshold: int = Field(default=10, ge=0, le=64, description="Similarity threshold (0-64)")
    algorithm: HashAlgorithm = Field(default=HashAlgorithm.AVERAGE, description="Hash algorithm")
    recursive: bool = Field(default=True, description="Scan subdirectories")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "directory": "/home/user/images",
                    "threshold": 10,
                    "algorithm": "average_hash",
                    "recursive": True
                }
            ]
        }
    }


class DeleteRequest(BaseModel):
    """Request to delete duplicate files"""
    files: List[str] = Field(..., description="List of file paths to delete")
    dry_run: bool = Field(default=True, description="Simulate deletion without actually deleting")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "files": ["/home/user/images/dup1.jpg", "/home/user/images/dup2.jpg"],
                    "dry_run": True
                }
            ]
        }
    }


class DeleteFromGroupsRequest(BaseModel):
    """Request to delete duplicates from scan results, keeping one per group"""
    groups: List[Dict[str, Any]] = Field(..., description="Duplicate groups from scan result")
    keep_strategy: str = Field(default="first", description="Which file to keep: 'first', 'largest', 'smallest'")
    dry_run: bool = Field(default=True, description="Simulate deletion without actually deleting")


# ============================================================================
# Response Models
# ============================================================================

class FileInfo(BaseModel):
    """Information about a file"""
    path: str
    filename: str
    size_bytes: int
    size_mb: float
    width: Optional[int] = 0
    height: Optional[int] = 0
    resolution: Optional[str] = "N/A"
    modified_time: Optional[str] = None
    created_time: Optional[str] = None
    exists: bool = True
    error: Optional[str] = None


class DuplicateGroup(BaseModel):
    """A group of duplicate files"""
    hash: str
    hash_algorithm: str = "md5"
    count: int
    files: List[FileInfo]


class SimilarFileInfo(BaseModel):
    """File info with similarity distance"""
    path: str
    filename: str
    size_bytes: int
    size_mb: float
    width: Optional[int] = 0
    height: Optional[int] = 0
    resolution: Optional[str] = "N/A"
    distance: int = 0
    exists: bool = True


class SimilarGroup(BaseModel):
    """A group of similar files"""
    reference_hash: str
    hash_algorithm: str = "average_hash"
    threshold: int
    similarity_count: int
    files: List[SimilarFileInfo]


class ScanMetadata(BaseModel):
    """Metadata for scan results"""
    scan_date: str
    scanned_directory: str
    total_images_scanned: int
    unique_images: int
    duplicate_groups: int
    total_duplicate_files: int
    space_can_free_bytes: int
    space_can_free_mb: float
    is_clean: bool


class SimilarScanMetadata(BaseModel):
    """Metadata for similar scan results"""
    scan_date: str
    scanned_directory: str
    similarity_threshold: int
    hash_algorithm: str
    total_images_scanned: int
    images_processed: int
    similar_groups_found: int
    total_similar_files: int
    removable_files: int
    estimated_space_bytes: int
    estimated_space_mb: float
    is_clean: bool


class DuplicateScanResponse(BaseModel):
    """Response from duplicate scan"""
    success: bool
    message: str
    metadata: ScanMetadata
    groups: List[DuplicateGroup]
    report_json: Optional[str] = None
    report_txt: Optional[str] = None


class SimilarScanResponse(BaseModel):
    """Response from similar scan"""
    success: bool
    message: str
    metadata: SimilarScanMetadata
    groups: List[SimilarGroup]
    report_json: Optional[str] = None
    report_txt: Optional[str] = None


class DeleteResult(BaseModel):
    """Result of a single file deletion"""
    path: str
    success: bool
    message: str
    size_freed: int = 0


class DeleteResponse(BaseModel):
    """Response from delete operation"""
    success: bool
    message: str
    dry_run: bool
    total_files: int
    deleted_count: int
    failed_count: int
    total_space_freed: int
    space_freed_mb: float
    results: List[DeleteResult]


class ReportSummary(BaseModel):
    """Summary of a saved report"""
    filename: str
    filepath: str
    type: str
    scan_date: str
    scanned_directory: str
    total_scanned: int
    groups_found: int
    is_clean: bool
    space_mb: float


class ReportsListResponse(BaseModel):
    """Response listing available reports"""
    success: bool
    count: int
    reports: List[ReportSummary]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    timestamp: str
    imagehash_available: bool


class TaskResponse(BaseModel):
    """Response for async task creation"""
    task_id: str
    status: TaskStatus
    message: str


class TaskStatusResponse(BaseModel):
    """Response for task status check"""
    task_id: str
    status: TaskStatus
    progress: int = 0
    message: str
    result: Optional[Dict[str, Any]] = None
