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


