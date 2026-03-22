from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    details: Any = None


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(_request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "invalid_request", "Request validation failed", exc.errors())

    @app.exception_handler(HTTPException)
    async def _handle_http_error(_request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else None
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return error_response(exc.status_code, "http_error", message, detail)

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error", exc_info=exc)
        return error_response(500, "internal_error", "Internal server error")


__all__ = ["ApiError", "error_response", "register_exception_handlers"]
