class BaseException(Exception):
    """This is the base class for all Base errors"""

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


class NoFilenameProvided(BaseException):
    """No filename provided"""

    pass


