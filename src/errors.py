import logging
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from src.exceptions import (
    FileTooLarge,
    ImageUploadFailed,
    InsufficientPermission,
    InvalidFileContent,
    InvalidFileType,
    NoFilenameProvided,
    NotFound,
    UnprocessableEntity,
)


def register_global_error_handlers(app: FastAPI):
    app.add_exception_handler(
        NotFound,
        create_exception_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            initial_detail={
                "status": "failure",
                "message": "Not found",
                "err_code": "not_found",
            },
        ),
    )

    app.add_exception_handler(
        InsufficientPermission,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "status": "failure",
                "message": "You do not have sufficient permissions to perform this action",
                "err_code": "insufficient_permission",
            },
        ),
    )
    
    app.add_exception_handler(
        NoFilenameProvided,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "status": "failure",
                "message": "The request could not be processed due to validation errors",
                "err_code": "no_filename_provided",
            },
        ),
    )

    app.add_exception_handler(
        UnprocessableEntity,
        create_exception_handler(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            initial_detail={
                "status": "failure",
                "message": "No filename provided",
                "err_code": "unprocessable_entity",
            },
        ),
    )

    app.add_exception_handler(
        InvalidFileType,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "status": "failure",
                "message": "Invalid file type",
                "err_code": "invalid_file_type",
            },
        ),
    )

    app.add_exception_handler(
        FileTooLarge,
        create_exception_handler(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            initial_detail={
                "status": "failure",
                "message": "File size exceeds maximum allowed size",
                "err_code": "file_too_large",
            },
        ),
    )

    app.add_exception_handler(
        InvalidFileContent,
        create_exception_handler(
            status_code=status.HTTP_400_BAD_REQUEST,
            initial_detail={
                "status": "failure",
                "message": "File must be an image",
                "err_code": "invalid_file_content",
            },
        ),
    )

    app.add_exception_handler(
        ImageUploadFailed,
        create_exception_handler(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            initial_detail={
                "status": "failure",
                "message": "Failed to upload image",
                "err_code": "image_upload_failed",
            },
        ),
    )
    
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore

    app.add_exception_handler(Exception, internal_server_error_handler)
    
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "status": "failure",
            "message": "Too many requests. Please slow down.",
            "err_code": "rate_limit_exceeded",
        },
    )


def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = exc.errors()
    modified_details = {}
    for error in details:
        field_name = error["loc"][-1]  # Get last element (field name)
        modified_details[field_name] = error["msg"]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "status": "failure",
            "message": "Validation error",
            "errors": modified_details,
        },
    )


def internal_server_error_handler(request, exc: Exception):

    logging.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={"status": "failure", "message": "Internal server error"},
    )


def create_exception_handler(
    status_code: int, initial_detail: Any
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # If the exception has a custom message, use it
        if hasattr(exc, "message") and exc.message:
            detail = initial_detail.copy()
            detail["message"] = exc.message
            return JSONResponse(content=detail, status_code=status_code)

        response_status_code = status_code
        if hasattr(exc, "status_code") and exc.status_code:
            response_status_code = getattr(exc, "status_code", status_code)

        return JSONResponse(content=initial_detail, status_code=response_status_code)

    return exception_handler
