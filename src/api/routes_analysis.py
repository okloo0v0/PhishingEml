"""POST /api/emails/analyze — strict three-way mutually exclusive input."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from src.api.deps import get_analysis_service
from src.api.responses import ok
from src.config import get_settings
from src.domain.errors import DomainError, ErrorCode
from src.domain.schemas import (
    AnalysisInput,
    EmailFileInput,
    to_jsonable,
    validate_analysis_input,
)
from src.services.analysis_service import AnalysisService

router = APIRouter()


@router.post("/emails/analyze")
async def analyze_email(
    request: Request,
    file: UploadFile | None = File(default=None),
    raw_text: str | None = Form(default=None),
    sample_id: str | None = Form(default=None),
    service: AnalysisService = Depends(get_analysis_service),
):
    settings = get_settings()

    file_input: EmailFileInput | None = None
    if file is not None:
        content = await file.read()
        file_input = EmailFileInput(
            filename=file.filename or "",
            content=content,
            content_type=file.content_type or "",
        )

    source = validate_analysis_input(
        AnalysisInput(file=file_input, raw_text=raw_text, sample_id=sample_id)
    )

    if source == "file":
        if len(file_input.content) > settings.max_upload_bytes:
            raise DomainError(ErrorCode.FILE_TOO_LARGE, "邮件文件不能超过 5 MB", 413)
        if not file_input.filename.lower().endswith(".eml"):
            raise DomainError(ErrorCode.INVALID_FILE_TYPE, "仅支持 .eml 文件", 400)
        content, filename = file_input.content, file_input.filename
    elif source == "raw_text":
        if len(raw_text) > settings.max_body_chars:
            raise DomainError(
                ErrorCode.VALIDATION_ERROR,
                f"邮件原文不能超过 {settings.max_body_chars} 个字符",
                400,
            )
        content, filename = raw_text.encode("utf-8"), "pasted.eml"
    else:  # sample_id
        sample_path = settings.sample_dir / f"{sample_id}.eml"
        if not sample_path.is_file():
            raise DomainError(ErrorCode.RECORD_NOT_FOUND, "演示样本不存在", 404)
        content, filename = sample_path.read_bytes(), sample_path.name

    result = service.analyze(content, filename)
    return ok(request, to_jsonable(result))
