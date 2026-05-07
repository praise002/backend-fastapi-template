from src.exceptions import BaseException


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
