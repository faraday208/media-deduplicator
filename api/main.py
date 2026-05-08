#!/usr/bin/env python3
"""
Duplicate Image Finder - FastAPI REST API
Gradio UI ve diğer tüketiciler için REST API endpoint'leri.

Usage:
    uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

    veya:
    python -m api.main
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import DuplicateScanner, SimilarScanner, Reporter, Hasher

# Import config
try:
    from config import MAX_WORKERS, API_HOST, API_PORT, SCAN_TIMEOUT, DELETE_TIMEOUT
except ImportError:
    MAX_WORKERS = os.cpu_count() or 4
    API_HOST = '0.0.0.0'
    API_PORT = 8001
    SCAN_TIMEOUT = 600
    DELETE_TIMEOUT = 60
from api.schemas import (
    ScanRequest, SimilarScanRequest, DeleteRequest, DeleteFromGroupsRequest,
    DuplicateScanResponse, SimilarScanResponse, DeleteResponse, DeleteResult,
    ScanMetadata, SimilarScanMetadata, DuplicateGroup, SimilarGroup,
    FileInfo, SimilarFileInfo, ReportsListResponse, ReportSummary,
    HealthResponse, TaskResponse, TaskStatusResponse, TaskStatus, HashAlgorithm
)


# ============================================================================
# Configuration
# ============================================================================

API_VERSION = "1.0.0"
API_TITLE = "Duplicate Image Finder API"
API_DESCRIPTION = """
Duplicate Image Finder REST API.

## Özellikler

* **Duplicate Tarama** - MD5 hash ile birebir aynı görselleri bul
* **Benzer Tarama** - Perceptual hash ile benzer görselleri bul
* **Silme** - Duplicate/benzer dosyaları sil
* **Raporlama** - JSON/TXT raporları oluştur ve listele

## Kullanım

HTTP POST ile çağrılır (Gradio UI veya curl/script'ler için):
- Method: POST
- URL: http://localhost:8001/api/v1/scan/duplicates
- Body: {"directory": "/path/to/images"}
"""

# Background task storage
tasks: Dict[str, Dict[str, Any]] = {}
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


# ============================================================================
# Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print(f"[{datetime.now().isoformat()}] {API_TITLE} v{API_VERSION} starting...")
    print(f"[{datetime.now().isoformat()}] Max workers: {MAX_WORKERS}")
    print(f"[{datetime.now().isoformat()}] imagehash available: {Hasher.is_perceptual_hash_available()}")
    yield
    # Shutdown
    executor.shutdown(wait=False)
    print(f"[{datetime.now().isoformat()}] {API_TITLE} shutting down...")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Helper Functions
# ============================================================================

def decode_path(path: str) -> str:
    """URL decode path - %20 -> space, etc."""
    from urllib.parse import unquote
    return unquote(path)


def validate_directory(directory: str) -> str:
    """Validate that directory exists and is accessible. Returns decoded path."""
    directory = decode_path(directory)
    path = Path(directory)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {directory}")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {directory}")
    return directory


def build_file_info(filepath: str) -> FileInfo:
    """Build FileInfo from filepath"""
    info = Reporter.get_file_info(filepath)
    return FileInfo(
        path=info.get('path', filepath),
        filename=info.get('filename', os.path.basename(filepath)),
        size_bytes=info.get('size_bytes', 0),
        size_mb=info.get('size_mb', 0.0),
        width=info.get('width', 0),
        height=info.get('height', 0),
        resolution=info.get('resolution', 'N/A'),
        modified_time=info.get('modified_time'),
        created_time=info.get('created_time'),
        exists=info.get('exists', True),
        error=info.get('error')
    )


def build_similar_file_info(file_data: dict) -> SimilarFileInfo:
    """Build SimilarFileInfo from file data"""
    filepath = file_data['path']
    info = Reporter.get_file_info(filepath)
    return SimilarFileInfo(
        path=info.get('path', filepath),
        filename=info.get('filename', os.path.basename(filepath)),
        size_bytes=info.get('size_bytes', 0),
        size_mb=info.get('size_mb', 0.0),
        width=info.get('width', 0),
        height=info.get('height', 0),
        resolution=info.get('resolution', 'N/A'),
        distance=int(file_data.get('distance', 0)),
        exists=info.get('exists', True)
    )


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/", tags=["Info"])
async def root():
    """API root - redirects to docs"""
    return {
        "service": API_TITLE,
        "version": API_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Info"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service=API_TITLE,
        version=API_VERSION,
        timestamp=datetime.now().isoformat(),
        imagehash_available=Hasher.is_perceptual_hash_available()
    )


# ============================================================================
# Duplicate Scan Endpoints
# ============================================================================

@app.post("/api/v1/scan/duplicates", response_model=DuplicateScanResponse, tags=["Scan"])
async def scan_duplicates(request: ScanRequest):
    """
    Scan directory for exact duplicate images using MD5 hash.

    Synchronous operation - waits for scan to complete.
    For large directories, use the async endpoint instead.
    """
    directory = validate_directory(request.directory)

    scanner = DuplicateScanner()
    result = scanner.find_duplicates(directory, recursive=request.recursive)

    # Save reports
    reporter = Reporter()
    json_path, txt_path = reporter.save_duplicate_report(result)

    # Build response
    groups = []
    for group in result.groups:
        groups.append(DuplicateGroup(
            hash=group['hash'],
            hash_algorithm=group.get('hash_algorithm', 'md5'),
            count=group['count'],
            files=[build_file_info(f) for f in group['files']]
        ))

    metadata = ScanMetadata(
        scan_date=datetime.now().isoformat(),
        scanned_directory=directory,
        total_images_scanned=result.total_scanned,
        unique_images=result.unique_count,
        duplicate_groups=len(result.groups),
        total_duplicate_files=result.duplicate_count,
        space_can_free_bytes=result.space_can_free,
        space_can_free_mb=result.space_can_free / (1024 ** 2),
        is_clean=not result.has_duplicates
    )

    message = "Temiz - duplicate bulunamadi" if not result.has_duplicates else f"{len(result.groups)} duplicate grup bulundu"

    return DuplicateScanResponse(
        success=True,
        message=message,
        metadata=metadata,
        groups=groups,
        report_json=json_path,
        report_txt=txt_path
    )


@app.post("/api/v1/scan/duplicates/async", response_model=TaskResponse, tags=["Scan"])
async def scan_duplicates_async(request: ScanRequest, background_tasks: BackgroundTasks):
    """
    Start async duplicate scan.

    Returns task_id immediately. Use /api/v1/tasks/{task_id} to check status.
    """
    validate_directory(request.directory)

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0,
        "message": "Task queued",
        "result": None
    }

    def run_scan():
        try:
            tasks[task_id]["status"] = TaskStatus.RUNNING
            tasks[task_id]["message"] = "Scanning..."

            scanner = DuplicateScanner()

            def progress_callback(current, total, message):
                if total > 0:
                    tasks[task_id]["progress"] = int((current / total) * 100)
                tasks[task_id]["message"] = message

            result = scanner.find_duplicates(
                request.directory,
                recursive=request.recursive,
                progress_callback=progress_callback
            )

            # Save reports
            reporter = Reporter()
            json_path, txt_path = reporter.save_duplicate_report(result)

            tasks[task_id]["status"] = TaskStatus.COMPLETED
            tasks[task_id]["progress"] = 100
            tasks[task_id]["message"] = "Scan completed"
            tasks[task_id]["result"] = {
                "total_scanned": result.total_scanned,
                "duplicate_groups": len(result.groups),
                "duplicate_files": result.duplicate_count,
                "space_can_free_mb": result.space_can_free / (1024 ** 2),
                "is_clean": not result.has_duplicates,
                "report_json": json_path,
                "report_txt": txt_path
            }
        except Exception as e:
            tasks[task_id]["status"] = TaskStatus.FAILED
            tasks[task_id]["message"] = str(e)

    background_tasks.add_task(run_scan)

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Duplicate scan task queued"
    )


# ============================================================================
# Similar Scan Endpoints
# ============================================================================

@app.post("/api/v1/scan/similar", response_model=SimilarScanResponse, tags=["Scan"])
async def scan_similar(request: SimilarScanRequest):
    """
    Scan directory for visually similar images using perceptual hashing.

    Threshold guide:
    - 0-5: Very similar (strict)
    - 6-10: Similar (recommended)
    - 11-15: Somewhat similar
    - 16+: Loose similarity
    """
    if not Hasher.is_perceptual_hash_available():
        raise HTTPException(
            status_code=503,
            detail="imagehash library not available. Install with: pip install imagehash"
        )

    directory = validate_directory(request.directory)

    scanner = SimilarScanner()
    result = scanner.find_similar(
        directory,
        threshold=request.threshold,
        algorithm=request.algorithm.value,
        recursive=request.recursive
    )

    # Save reports
    reporter = Reporter()
    json_path, txt_path = reporter.save_similar_report(
        result,
        threshold=request.threshold,
        algorithm=request.algorithm.value
    )

    # Build response
    groups = []
    for group in result.groups:
        groups.append(SimilarGroup(
            reference_hash=group.get('reference_hash', ''),
            hash_algorithm=group.get('hash_algorithm', request.algorithm.value),
            threshold=group.get('threshold', request.threshold),
            similarity_count=group.get('similarity_count', len(group['files'])),
            files=[build_similar_file_info(f) for f in group['files']]
        ))

    total_similar = sum(g.get('similarity_count', len(g['files'])) for g in result.groups)
    removable = sum(g.get('similarity_count', len(g['files'])) - 1 for g in result.groups)

    metadata = SimilarScanMetadata(
        scan_date=datetime.now().isoformat(),
        scanned_directory=directory,
        similarity_threshold=request.threshold,
        hash_algorithm=request.algorithm.value,
        total_images_scanned=result.total_scanned,
        images_processed=result.unique_count,
        similar_groups_found=len(result.groups),
        total_similar_files=total_similar,
        removable_files=removable,
        estimated_space_bytes=result.space_can_free,
        estimated_space_mb=result.space_can_free / (1024 ** 2),
        is_clean=not result.has_duplicates
    )

    message = "Temiz - benzer resim bulunamadi" if not result.has_duplicates else f"{len(result.groups)} benzer grup bulundu"

    return SimilarScanResponse(
        success=True,
        message=message,
        metadata=metadata,
        groups=groups,
        report_json=json_path,
        report_txt=txt_path
    )


@app.post("/api/v1/scan/similar/async", response_model=TaskResponse, tags=["Scan"])
async def scan_similar_async(request: SimilarScanRequest, background_tasks: BackgroundTasks):
    """
    Start async similar image scan.

    Returns task_id immediately. Use /api/v1/tasks/{task_id} to check status.
    """
    if not Hasher.is_perceptual_hash_available():
        raise HTTPException(
            status_code=503,
            detail="imagehash library not available"
        )

    directory = validate_directory(request.directory)

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0,
        "message": "Task queued",
        "result": None
    }

    def run_scan():
        try:
            tasks[task_id]["status"] = TaskStatus.RUNNING
            tasks[task_id]["message"] = "Scanning..."

            scanner = SimilarScanner()

            def progress_callback(current, total, message):
                if total > 0:
                    tasks[task_id]["progress"] = int((current / total) * 100)
                tasks[task_id]["message"] = message

            result = scanner.find_similar(
                directory,
                threshold=request.threshold,
                algorithm=request.algorithm.value,
                recursive=request.recursive,
                progress_callback=progress_callback
            )

            reporter = Reporter()
            json_path, txt_path = reporter.save_similar_report(
                result,
                threshold=request.threshold,
                algorithm=request.algorithm.value
            )

            total_similar = sum(g.get('similarity_count', len(g['files'])) for g in result.groups)
            removable = sum(g.get('similarity_count', len(g['files'])) - 1 for g in result.groups)

            tasks[task_id]["status"] = TaskStatus.COMPLETED
            tasks[task_id]["progress"] = 100
            tasks[task_id]["message"] = "Scan completed"
            tasks[task_id]["result"] = {
                "total_scanned": result.total_scanned,
                "similar_groups": len(result.groups),
                "similar_files": total_similar,
                "removable_files": removable,
                "space_can_free_mb": result.space_can_free / (1024 ** 2),
                "is_clean": not result.has_duplicates,
                "report_json": json_path,
                "report_txt": txt_path
            }
        except Exception as e:
            tasks[task_id]["status"] = TaskStatus.FAILED
            tasks[task_id]["message"] = str(e)

    background_tasks.add_task(run_scan)

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Similar scan task queued"
    )


# ============================================================================
# Delete Endpoints
# ============================================================================

@app.post("/api/v1/delete", response_model=DeleteResponse, tags=["Delete"])
async def delete_files(request: DeleteRequest):
    """
    Delete specified files.

    Use dry_run=true to simulate without actually deleting.
    """
    results = []
    total_freed = 0
    deleted_count = 0
    failed_count = 0

    for filepath in request.files:
        path = Path(filepath)

        if not path.exists():
            results.append(DeleteResult(
                path=filepath,
                success=False,
                message="File not found",
                size_freed=0
            ))
            failed_count += 1
            continue

        try:
            size = path.stat().st_size

            if request.dry_run:
                results.append(DeleteResult(
                    path=filepath,
                    success=True,
                    message="Would delete (dry run)",
                    size_freed=size
                ))
            else:
                path.unlink()
                results.append(DeleteResult(
                    path=filepath,
                    success=True,
                    message="Deleted",
                    size_freed=size
                ))

            total_freed += size
            deleted_count += 1

        except Exception as e:
            results.append(DeleteResult(
                path=filepath,
                success=False,
                message=str(e),
                size_freed=0
            ))
            failed_count += 1

    return DeleteResponse(
        success=failed_count == 0,
        message=f"{'Dry run: ' if request.dry_run else ''}{deleted_count} files processed, {failed_count} failed",
        dry_run=request.dry_run,
        total_files=len(request.files),
        deleted_count=deleted_count,
        failed_count=failed_count,
        total_space_freed=total_freed,
        space_freed_mb=total_freed / (1024 ** 2),
        results=results
    )


def get_image_resolution(filepath: str) -> tuple[int, int]:
    """Get image resolution (width, height). Returns (0, 0) on error."""
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            return img.size  # (width, height)
    except Exception:
        return (0, 0)


def get_file_score(filepath: str, strategy: str) -> tuple:
    """
    Calculate file score for sorting based on strategy.
    Returns tuple for sorting (higher = better to keep).
    """
    path = Path(filepath)
    size = path.stat().st_size if path.exists() else 0

    if strategy == 'largest':
        return (size,)
    elif strategy == 'smallest':
        return (-size,)  # Negative so smaller comes first
    elif strategy == 'highest_resolution':
        width, height = get_image_resolution(filepath)
        pixels = width * height
        # Primary: resolution, Secondary: file size (for same resolution)
        return (pixels, size)
    elif strategy == 'best':
        # Best = largest file size, then highest resolution
        width, height = get_image_resolution(filepath)
        pixels = width * height
        return (size, pixels)
    else:  # 'first' or unknown
        return (0,)  # Keep original order


@app.post("/api/v1/delete/from-groups", response_model=DeleteResponse, tags=["Delete"])
async def delete_from_groups(request: DeleteFromGroupsRequest):
    """
    Delete duplicates from scan result groups, keeping one file per group.

    keep_strategy options:
    - 'first': Keep the first file in each group (original order)
    - 'largest': Keep the largest file (by byte size)
    - 'smallest': Keep the smallest file (by byte size)
    - 'highest_resolution': Keep the highest resolution image
    - 'best': Keep the best quality (highest resolution, then largest size)
    """
    files_to_delete = []

    for group in request.groups:
        files = group.get('files', [])
        if len(files) < 2:
            continue

        # Extract file paths
        file_paths = []
        for f in files:
            if isinstance(f, dict):
                file_paths.append(f.get('path', f.get('filepath', '')))
            else:
                file_paths.append(str(f))

        file_paths = [f for f in file_paths if f and Path(f).exists()]

        if len(file_paths) < 2:
            continue

        # Determine which file to keep based on strategy
        if request.keep_strategy == 'first':
            # Keep original order, first file stays
            pass
        else:
            # Sort by score (descending - best first)
            file_paths.sort(
                key=lambda f: get_file_score(f, request.keep_strategy),
                reverse=True
            )

        # Keep first, delete rest
        files_to_delete.extend(file_paths[1:])

    # Use the delete endpoint logic
    delete_request = DeleteRequest(files=files_to_delete, dry_run=request.dry_run)
    return await delete_files(delete_request)


# ============================================================================
# Reports Endpoints
# ============================================================================

@app.get("/api/v1/reports", response_model=ReportsListResponse, tags=["Reports"])
async def list_reports(
    report_type: Optional[str] = Query(None, description="Filter by type: 'duplicate' or 'similar'")
):
    """List all saved reports"""
    reporter = Reporter()
    reports = reporter.get_reports(report_type)

    return ReportsListResponse(
        success=True,
        count=len(reports),
        reports=[ReportSummary(**r) for r in reports]
    )


@app.get("/api/v1/reports/{filename}", tags=["Reports"])
async def get_report(filename: str):
    """Get a specific report by filename"""
    reporter = Reporter()
    report = reporter.load_report(filename)

    if report is None:
        raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

    return report


@app.delete("/api/v1/reports/{filename}", tags=["Reports"])
async def delete_report(filename: str):
    """Delete a report"""
    reporter = Reporter()
    success, message = reporter.delete_report(filename)

    if not success:
        raise HTTPException(status_code=404, detail=message)

    return {"success": True, "message": message}


# ============================================================================
# Task Management Endpoints
# ============================================================================

@app.get("/api/v1/tasks/{task_id}", response_model=TaskStatusResponse, tags=["Tasks"])
async def get_task_status(task_id: str):
    """Get status of an async task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    task = tasks[task_id]
    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress", 0),
        message=task.get("message", ""),
        result=task.get("result")
    )


@app.get("/api/v1/tasks", tags=["Tasks"])
async def list_tasks():
    """List all tasks"""
    return {
        "count": len(tasks),
        "tasks": {
            task_id: {
                "status": task["status"],
                "progress": task.get("progress", 0),
                "message": task.get("message", "")
            }
            for task_id, task in tasks.items()
        }
    }


@app.delete("/api/v1/tasks/{task_id}", tags=["Tasks"])
async def delete_task(task_id: str):
    """Delete a completed task from memory"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    if tasks[task_id]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete running task")

    del tasks[task_id]
    return {"success": True, "message": f"Task {task_id} deleted"}


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level="info"
    )
