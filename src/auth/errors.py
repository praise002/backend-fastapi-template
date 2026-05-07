from fastapi import FastAPI, status

from src.auth.exceptions import (
    AccessTokenRequired,
    AccountNotVerified,
    GoogleAuthenticationFailed,
    InvalidCredentials,
    InvalidOldPassword,
    InvalidOtp,
    InvalidToken,
    NotAuthenticated,
    PasswordMismatch,
    PasswordSameAsOld,
    RefreshTokenRequired,
    RevokedToken,
    UserAlreadyExists,
    UsernameAlreadyExists,
    UserNotActive,
)
from src.errors import create_exception_handler


def register_auth_error_handlers(app: FastAPI):
    """
    Registers exception handlers for the authentication module.
    """
    app.add_exception_handler(
        NotAuthenticated,
        create_exception_handler(
            status.HTTP_401_UNAUTHORIZED,
            {"message": "Not Authenticated", "err_code": "unauthorized"},
        ),
    )
    app.add_exception_handler(
        InvalidToken,
        create_exception_handler(
            status.HTTP_401_UNAUTHORIZED,
            {"message": "Invalid token or token expired", "err_code": "invalid_token"},
        ),
    )
    app.add_exception_handler(
        UserAlreadyExists,
        create_exception_handler(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": "User with email already exists", "err_code": "user_exists"},
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

  

