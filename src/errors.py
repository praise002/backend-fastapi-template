import logging
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded


def register_all_errors(app: FastAPI):
    app.add_exception_handler(
        NotAuthenticated,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "status": "failure",
                "message": "Not Authenticated",
                "err_code": "unauthorized",
            },
        ),
    )

    app.add_exception_handler(
        UserAlreadyExists,
        create_exception_handler(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            initial_detail={
                "status": "failure",
                "message": "User with email already exists",
                "err_code": "user_exists",
            },
        ),
    )

    app.add_exception_handler(
        UsernameAlreadyExists,
        create_exception_handler(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            initial_detail={
                "status": "failure",
                "message": "User with username already exists",
                "err_code": "username_exists",
            },
        ),
    )

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
        InvalidCredentials,
        create_exception_handler(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            initial_detail={
                "status": "failure",
                "message": "Invalid email or password",
                "err_code": "invalid_email_or_password",
            },
        ),
    )

    app.add_exception_handler(
        InvalidOtp,
        create_exception_handler(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            initial_detail={
                "status": "failure",
                # "message": "Invalid otp or otp expired",
                "message": "Invalid OTP",
                "err_code": "invalid_otp",
            },
        ),
    )

    app.add_exception_handler(
        InvalidToken,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "status": "failure",
                "message": "Invalid token or token expired",
                "err_code": "invalid_token",
            },
        ),
    )

    app.add_exception_handler(
        GoogleAuthenticationFailed,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "status": "failure",
                "message": "Google authentication failed",
                "err_code": "google_auth_failed",
            },
        ),
    )

    app.add_exception_handler(
        RevokedToken,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "status": "failure",
                "message": "Token is invalid or has been revoked",
                "err_code": "token_revoked",
            },
        ),
    )

    app.add_exception_handler(
        AccessTokenRequired,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "status": "failure",
                "message": "Please provide a valid access token",
                "err_code": "access_token_required",
            },
        ),
    )

    app.add_exception_handler(
        RefreshTokenRequired,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "status": "failure",
                "message": "Please provide a valid refresh token",
                "err_code": "refresh_token_required",
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
        AccountNotVerified,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "status": "failure",
                "message": "Account not verified.",
                "err_code": "account_not_verified",
            },
        ),
    )

    app.add_exception_handler(
        UserNotActive,
        create_exception_handler(
            status_code=status.HTTP_403_FORBIDDEN,
            initial_detail={
                "status": "failure",
                "message": "Your account has been disabled. Please contact support for assistance",
                "err_code": "forbidden",
            },
        ),
    )

    app.add_exception_handler(
        PasswordMismatch,
        create_exception_handler(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            initial_detail={
                "status": "failure",
                "message": "New password and confirm password do not match",
                "err_code": "password_mismatch",
            },
        ),
    )

    app.add_exception_handler(
        InvalidOldPassword,
        create_exception_handler(
            status_code=status.HTTP_401_UNAUTHORIZED,
            initial_detail={
                "status": "failure",
                "message": "Invalid old password",
                "err_code": "invalid_old_password",
            },
        ),
    )

    app.add_exception_handler(
        PasswordSameAsOld,
        create_exception_handler(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            initial_detail={
                "status": "failure",
                "message": "New password cannot be the same as your current password",
                "err_code": "password_same_as_old",
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



class BaseException(Exception):
    """This is the base class for all Base errors"""

    pass


class NotAuthenticated(BaseException):
    """User is not authenticated"""

    pass


class InvalidOtp(BaseException):
    """User has provided an invalid or expired otp"""

    pass


class InvalidToken(BaseException):
    """User has provided an invalid or expired token"""

    pass


class RevokedToken(BaseException):
    """User has provided a token that has been revoked"""

    pass


class AccessTokenRequired(BaseException):
    """User has provided a refresh token when an access token is needed"""

    pass


class RefreshTokenRequired(BaseException):
    """User has provided an access token when a refresh token is needed"""

    pass


class UserAlreadyExists(BaseException):
    """User has provided an email for a user who exists during sign up"""

    pass


class UsernameAlreadyExists(BaseException):
    """Username exists"""

    pass


class InvalidCredentials(BaseException):
    """User has provided wrong email or password during login"""

    pass


class UnprocessableEntity(BaseException):
    """
    Raised when the request is well-formed but contains semantic errors
    that prevent processing.

    This covers validation failures, business logic errors, and constraint
    violations that don't fit specific exception types like UserAlreadyExists
    or PasswordMismatch.

    Examples:
    - Invalid field values that pass basic type checking but fail business rules
    - Constraints violations (e.g., min/max length, patterns, ranges)
    - Related entity validation errors
    - Duplicate resource conflicts
    - Invalid state transitions

    Use this for general 422 errors when more specific exceptions don't apply.
    """

    def __init__(
        self,
        message: str = "The request could not be processed due to validation errors",
        err_code: str = "unprocessable_entity",
    ):
        self.message = message
        self.err_code = err_code
        super().__init__(self.message)


class InsufficientPermission(BaseException):
    """User does not have the neccessary permissions to perform an action"""

    def __init__(
        self,
        message: str = "You do not have sufficient permissions to perform this action",
    ):
        self.message = message
        super().__init__(self.message)


class NotFound(BaseException):
    """Resource not found"""

    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(self.message)


class InvalidFileType(BaseException):
    """Invalid file type uploaded"""

    def __init__(self, message: str = "Invalid file type"):
        self.message = message
        super().__init__(self.message)


class FileTooLarge(BaseException):
    """File exceeds maximum allowed size"""

    def __init__(self, message: str = "File size exceeds maximum allowed size"):
        self.message = message
        super().__init__(self.message)


class InvalidFileContent(BaseException):
    """File content is invalid or corrupted"""

    def __init__(self, message: str = "File must be an image"):
        self.message = message
        super().__init__(self.message)


class ImageUploadFailed(BaseException):
    """Image upload to Cloudinary failed"""

    def __init__(self, message: str = "Failed to upload image"):
        self.message = message
        super().__init__(self.message)


class AccountNotVerified(BaseException):
    """Account not yet verified"""

    pass


class UserNotActive(BaseException):
    """User not active"""

    pass


class PasswordMismatch(BaseException):
    """New password and confirm password deosn't match"""

    pass


class InvalidOldPassword(BaseException):
    """Invalid old password"""

    pass


class PasswordSameAsOld(BaseException):
    """New password is the same as the old password"""

    pass


class GoogleAuthenticationFailed(BaseException):
    """Google authentication failed"""

    pass


class NoFilenameProvided(BaseException):
    """No filename provided"""

    pass


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
