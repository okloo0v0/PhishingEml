"""Unified response envelope: {success, data|error, request_id}."""

from __future__ import annotations

import uuid
from typing import Any


def request_id(request) -> str:
    return getattr(request.state, "request_id", None) or uuid.uuid4().hex


def ok(request, data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "request_id": request_id(request)}


def error_body(request, code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": {"code": code, "message": message},
        "request_id": request_id(request),
    }
