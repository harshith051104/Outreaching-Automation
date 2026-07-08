"""
File upload API routes.

Handles file uploads for the chatbot and email attachments.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_user
from app.services.file_upload_service import (
    upload_file,
    get_user_files,
    get_file,
    delete_file,
)

router = APIRouter(prefix="/files", tags=["File Upload"])


@router.post("/upload", summary="Upload a file")
async def upload(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a file (PDF, image, document, etc.)."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Upload request: filename={file.filename}, content_type={file.content_type}")
    
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    # ponytail: whitelist safe extensions to prevent arbitrary file upload & XSS
    import os
    ext = os.path.splitext(file.filename)[1].lower() if "." in file.filename else ""
    allowed_extensions = {".csv", ".xlsx", ".xls", ".pdf", ".png", ".jpg", ".jpeg", ".txt", ".docx", ".doc"}
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension {ext} not allowed. Supported formats: CSV, Excel, PDF, images, Word, text."
        )
    
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    logger.info(f"File content length: {len(content)} bytes ({file_size_mb:.2f} MB)")
    
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file"
        )
    
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large ({file_size_mb:.1f}MB). Max 50MB."
        )
    
    result = await upload_file(
        user_id=current_user["id"],
        file_content=content,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
    )
    
    logger.info(f"Upload successful: {result}")
    return result


@router.get("", summary="List uploaded files")
async def list_files(
    current_user: dict = Depends(get_current_user),
):
    """List all uploaded files for the current user."""
    return await get_user_files(current_user["id"])


@router.get("/{file_id}", summary="Get file info")
async def get_file_info(
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get metadata for a specific file."""
    file = await get_file(file_id, current_user["id"])
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    return file


@router.delete("/{file_id}", summary="Delete file")
async def delete(
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete an uploaded file."""
    deleted = await delete_file(file_id, current_user["id"])
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    return {"status": "deleted", "file_id": file_id}


@router.get("/{file_id}/download", summary="Download file")
async def download(
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Download an uploaded file."""
    import os
    from fastapi.responses import FileResponse
    
    file = await get_file(file_id, current_user["id"])
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    file_path = file.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )
    
    return FileResponse(
        path=file_path,
        filename=file.get("original_filename", "file"),
        media_type=file.get("content_type", "application/octet-stream"),
    )