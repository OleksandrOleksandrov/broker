"""PDF compression router."""

import io
import os
import zipfile
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..utils.pdf import compress_single_pdf

router = APIRouter(prefix="/api", tags=["pdf"])


@router.post("/compress-pdf")
async def compress_pdf(
    files: List[UploadFile] = File(...),
    max_size_kb: int = Form(495),
    remove_color: bool = Form(True),
):
    if not files:
        raise HTTPException(status_code=400, detail="Не завантажено жодного файлу")

    for file in files:
        if not file.content_type or "pdf" not in file.content_type.lower():
            raise HTTPException(
                status_code=400, detail=f"Файл '{file.filename}' має бути PDF"
            )

    compressed_files = []
    seen_filenames = {}

    for file in files:
        pdf_bytes = await file.read()
        try:
            compressed_bytes = compress_single_pdf(
                pdf_bytes, max_size_kb, remove_color
            )
        except ValueError as err:
            raise HTTPException(
                status_code=422,
                detail=f"Не вдалося стиснути файл '{file.filename}' до {max_size_kb} KB. {err}",
            )

        original_name = file.filename or "document.pdf"
        if original_name in seen_filenames:
            seen_filenames[original_name] += 1
            name, ext = os.path.splitext(original_name)
            output_filename = f"compressed_{name}_{seen_filenames[original_name]}{ext}"
        else:
            seen_filenames[original_name] = 0
            output_filename = f"compressed_{original_name}"

        compressed_files.append((output_filename, compressed_bytes))

    if len(compressed_files) == 1:
        filename, compressed_bytes = compressed_files[0]
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(
            io.BytesIO(compressed_bytes),
            headers=headers,
            media_type="application/pdf",
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, compressed_bytes in compressed_files:
            zip_file.writestr(filename, compressed_bytes)

    zip_buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="compressed_pdfs.zip"'}
    return StreamingResponse(
        zip_buffer,
        headers=headers,
        media_type="application/zip",
    )