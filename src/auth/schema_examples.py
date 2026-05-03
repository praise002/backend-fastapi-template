from src.auth.schemas import (
    ACCESS_TOKEN_EXAMPLE,
    EMAIL_EXAMPLE,
    FAILURE_EXAMPLE,
    REFRESH_TOKEN_EXAMPLE,
)

VALIDATION_ERROR = {
    "value": {"detail": [{"loc": ["string", 0], "msg": "string", "type": "string"}]},
}

UNAUTHORIZED = {
    "content": {
        "application/json": {
            "example": {
                "status": FAILURE_EXAMPLE,
                "message": "Please provide a valid access token.",
                "err_code": "access_token_required",
            }
        }
    }
}

REGISTER_RESPONSES = {
    200: {
        "content": {
            "application/json": {
                "example": {
                    "status": "success",
                    "message": "Account Created! Check email to verify your account",
                    "email": EMAIL_EXAMPLE,
                }
            }
        },
    },
    422: {
        "content": {
            "application/json": {
                "examples": {
                    "user_email_exists": {
                        "value": {
                            "status": "failure",
                            "message": "User with email already exists.",
                            "err_code": "user_exists",
                        },
                    },
                    "username_exists": {
                        "value": {
                            "status": "failure",
                            "message": "User with username already exists.",
                            "err_code": "username_exists",
                        },
                    },
                    "validation_error": VALIDATION_ERROR,
                }
            }
        },
    },
}


VERIFY_EMAIL_RESPONSES = {
    200: {
        "description": "Email verification successful",
        "content": {
            "application/json": {
                "examples": {
                    "verification_success": {
                        "value": {
                            "status": "success",
                            "message": "Email verified successfully",
                        },
                    },
                    "email_already_verified": {
                        "value": {
                            "status": "success",
                            "message": "Email address already verified. No OTP sent",
                        },
                    },
                }
            }
        },
    },
    422: {
        "content": {
            "application/json": {
                "examples": {
                    "invalid_otp": {
                        "value": {
                            "status": "failure",
                            "message": "Invalid otp or otp expired.",
                            "err_code": "invalid_otp",
                        },
                    },
                    "user_not_found": {
                        "value": {
                            "status": "failure",
                            "message": "User not found.",
                            "err_code": "user_not_found",
                        },
                    },
                    "validation_error": VALIDATION_ERROR,
                }
            }
        },
    },
}

RESEND_OTP_RESPONSES = {
    200: {
        "description": "OTP resent or email already verified",
        "content": {
            "application/json": {
                "examples": {
                    "otp_sent": {
                        "value": {
                            "status": "success",
                            "message": "OTP sent successfully",
                        },
                    },
                    "already_verified": {
                        "value": {
                            "status": "success",
                            "message": "Email address already verified. No OTP sent",
                        },
                    },
                }
            }
        },
    },
    422: {
        "content": {
            "application/json": {
                "examples": {
                    "user_not_found": {
                        "value": {
                            "status": "failure",
                            "message": "User not found.",
                            "err_code": "user_not_found",
                        },
                    },
                    "validation_error": VALIDATION_ERROR,
                }
            }
        },
    },
}

LOGIN_RESPONSES = {
    200: {
        "content": {
            "application/json": {
                "example": {
                    "login_success": {
                        "value": {
                            "status": "success",
                            "message": "Login successful",
                            "access_token": ACCESS_TOKEN_EXAMPLE,
                            "refresh_token": REFRESH_TOKEN_EXAMPLE,
                        }
                    }
                }
            }
        }
    },
    401: {
        "content": {
            "application/json": {
                "example": {
                    "invalid_credentials": {
                        "value": {
                            "status": "failure",
                            "message": "No active account found with the given credentials",
                            "error_code": "unauthorized",
                        }
                    }
                }
            }
        }
    },
    403: {
        "content": {
            "application/json": {
                "examples": {
                    "email_not_verified": {
                        "value": {
                            "status": "failure",
                            "message": "Email not verified. Please verify your email before logging in",
                            "err_code": "account_not_verified",
                        },
                    },
                    "account_disabled": {
                        "value": {
                            "status": "failure",
                            "message": "Your account has been disabled. Please contact support for assistance",
                            "err_code": "user_not_active",
                        },
                    },
                }
            }
        },
    },
}

REFRESH_TOKEN_RESPONSES = {
    200: {
        "content": {
            "application/json": {
                "example": {
                    "message": "Token refreshed successfully",
                    "access_token": ACCESS_TOKEN_EXAMPLE,
                    "refresh_token": REFRESH_TOKEN_EXAMPLE,
                }
            }
        }
    },
    401: {
        "content": {
            "application/json": {
                "example": {
                    "status": "failure",
                    "message": "Invalid token or token expired.",
                    "resolution": "Please get a new token",
                    "error_code": "invalid_token",
                }
            }
        },
    },
}


LOGOUT_RESPONSES = {
    200: {
        "content": {
            "application/json": {
                "example": {
                    "status": "success",
                    "message": "Logged Out successfully",
                }
            }
        }
    },
    401: {
        "content": {
            "application/json": {
                "example": {
                    "status": "failure",
                    "message": "Please provide a valid refresh token.",
                    "resolution": "Please get a refresh token",
                    "error_code": "refresh_token_required",
                }
            }
        }
    },
}

PASSWORD_RESET_REQUEST_RESPONSES = {
    200: {
        "description": "Password reset email sent",
        "content": {
            "application/json": {
                "example": {
                    "message": "Please check your email for instructions to reset your password",
                }
            }
        },
    },
}

PASSWORD_RESET_VERIFY_RESPONSES = {
    200: {
        "content": {
            "application/json": {
                "example": {
                    "message": "OTP verified, proceed to set a new password",
                }
            }
        }
    },
    422: {
        "content": {
            "application/json": {
                "examples": {
                    "invalid_otp": {
                        "value": {
                            "status": "failure",
                            "message": "Invalid or expired OTP.",
                            "err_code": "invalid_otp",
                        },
                    },
                    "user_not_found": {
                        "value": {
                            "status": "failure",
                            "message": "User not found.",
                            "err_code": "user_not_found",
                        },
                    },
                    "validation_error": VALIDATION_ERROR,
                }
            }
        },
    },
}

PASSWORD_RESET_COMPLETE_RESPONSES = {
    200: {
        "description": "Password reset completed",
        "content": {
            "application/json": {
                "example": {
                    "message": "Your password has been reset, proceed to login",
                }
            }
        },
    },
    422: {
        "content": {
            "application/json": {
                "examples": {
                    "user_not_found": {
                        "value": {
                            "status": "failure",
                            "message": "User not found.",
                            "err_code": "user_not_found",
                        },
                    },
                    "validation_error": VALIDATION_ERROR,
                }
            }
        },
    },
}

PASSWORD_CHANGE_RESPONSES = {
    200: {
        "content": {
            "application/json": {
                "example": {
                    "status": "success",
                    "message": "Password changed successfully",
                    "access_token": ACCESS_TOKEN_EXAMPLE,
                    "refresh_token": REFRESH_TOKEN_EXAMPLE,
                }
            }
        },
    },
    422: {
        "content": {
            "application/json": {
                "examples": {
                    "password_mismatch": {
                        "value": {
                            "status": "failure",
                            "message": "New password and confirm password do not match.",
                            "err_code": "password_mismatch",
                        },
                    },
                    "invalid_old_password": {
                        "value": {
                            "status": "failure",
                            "message": "Invalid old password.",
                            "err_code": "invalid_old_password",
                        },
                    },
                    "validation_error": VALIDATION_ERROR,
                }
            }
        }
    },
    401: {
        "content": {
            "application/json": {
                "example": {
                    "status": "failure",
                    "message": "Please provide a valid access token.",
                    "resolution": "Please get an access token",
                    "err_code": "access_token_required",
                }
            }
        },
    },
}

LOGOUT_ALL_RESPONSES = {
    200: {
        "content": {
            "application/json": {
                "example": {
                    "message": "Logged out of all devices successfully",
                }
            }
        },
    },
    401: {
        "content": {
            "application/json": {
                "example": {
                    "status": "failure",
                    "message": "Please provide a valid access token.",
                    "resolution": "Please get an access token",
                    "err_code": "access_token_required",
                }
            }
        },
    },
}


# NOTE: DOCS SHOWS 422 BY DEFAULT IF THERE IS A 422 ERROR FOR EXAMPLES
