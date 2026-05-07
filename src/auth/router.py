"""
Controller / Route Handler Layer
==================================
Outermost application layer. Handles incoming HTTP requests and delegates
to the service layer for all business logic.

Dependency direction: inward only.
  - Imports from: services, dependencies, domain/schemas, providers, infrastructure
  - Must NOT be imported by any inner layer

Controllers are deliberately thin — they:
  1. Extract validated input (via Pydantic schemas or dependency injection)
  2. Call a single service method per logical operation
  3. Map the result to an HTTP response

If a controller grows complex logic, move it to the service layer.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from config import Config
from src.auth.config import auth_settings
from src.auth.dependencies import (
    RefreshTokenBearer,
    RoleChecker,
    get_current_user,
    get_redis,
)
from src.auth.errors import (
    AccountNotVerified,
    GoogleAuthenticationFailed,
    InvalidOldPassword,
    InvalidOtp,
    PasswordMismatch,
    PasswordSameAsOld,
    UserAlreadyExists,
    UsernameAlreadyExists,
    UserNotActive,
)
from src.auth.oauth_config import oauth
from src.auth.providers.background_tasks import upload_profile_picture_task
from src.auth.redis import RedisService
from src.auth.schema_examples import (
    LOGIN_RESPONSES,
    LOGOUT_ALL_RESPONSES,
    LOGOUT_RESPONSES,
    PASSWORD_CHANGE_RESPONSES,
    PASSWORD_RESET_COMPLETE_RESPONSES,
    PASSWORD_RESET_REQUEST_RESPONSES,
    PASSWORD_RESET_VERIFY_RESPONSES,
    REFRESH_TOKEN_RESPONSES,
    REGISTER_RESPONSES,
    RESEND_OTP_RESPONSES,
    VERIFY_EMAIL_RESPONSES,
)
from src.auth.schemas import (
    OtpVerify,
    PasswordChangeModel,
    PasswordResetConfirmModel,
    PasswordResetModel,
    PasswordResetVerifyOtpModel,
    SendOtp,
    UserCreate,
    UserCreateOAuth,
    UserLoginModel,
    UserRegistrationResponse,
)
from src.auth.security import hash_password, verify_password
from src.auth.service import UserService
from src.db.database import get_session
from src.exceptions import NotFound
from src.limiter import limiter
from src.mail import send_email_by_type

router = APIRouter()

_user_service = UserService()
role_checker = RoleChecker(["admin", "user"])



# Registration & email verification

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRegistrationResponse,
    description="Register a new user account",
    responses=REGISTER_RESPONSES,  # type: ignore
)
@limiter.limit("5/minute")
async def create_user_account(
    request: Request,
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    if await _user_service.user_exists(user_data.email, session):
        raise UserAlreadyExists()

    if await _user_service.username_exists(user_data.username, session):
        raise UsernameAlreadyExists()

    new_user = await _user_service.create_user(user_data, session)
    otp = await _user_service.generate_otp(new_user, session)

    send_email_by_type(
        background_tasks, "activate", new_user.email, new_user.first_name, otp=str(otp)
    )

    return {
        "status": "success",
        "message": "Account created! Check your email to verify your account.",
        "email": new_user.email,
    }


@router.post(
    "/account-verification",
    status_code=status.HTTP_200_OK,
    description="Verify a user's email address via OTP",
    responses=VERIFY_EMAIL_RESPONSES,  # type: ignore
)
@limiter.limit("5/minute")
async def verify_user_account(
    request: Request,
    data: OtpVerify,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    user = await _user_service.get_user_by_email(data.email, session)
    if not user:
        raise NotFound("User not found")

    otp_record = await _user_service.get_otp_by_user(str(user.id), data.otp, session)
    if not otp_record or not otp_record.is_valid:
        raise InvalidOtp()

    if user.is_email_verified:
        return {"status": "success", "message": "Email address already verified."}

    await _user_service.update_user(user, {"is_email_verified": True}, session)
    await _user_service.invalidate_otps(user, session)

    send_email_by_type(background_tasks, "welcome", user.email, user.first_name)

    return {"status": "success", "message": "Email verified successfully."}


@router.post(
    "/verification/email-resend",
    status_code=status.HTTP_200_OK,
    description="Resend OTP for email verification",
    responses=RESEND_OTP_RESPONSES,  # type: ignore
)
async def resend_verification_email(
    data: SendOtp,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    user = await _user_service.get_user_by_email(data.email, session)
    if not user:
        raise NotFound("User not found")

    if user.is_email_verified:
        return {
            "status": "success",
            "message": "Email address already verified. No OTP sent.",
        }

    otp = await _user_service.generate_otp(user, session)
    send_email_by_type(
        background_tasks, "activate", user.email, user.first_name, otp=str(otp)
    )

    return {"status": "success", "message": "OTP sent successfully"}



# Authentication (login / refresh / logout)

@router.post(
    "/token",
    status_code=status.HTTP_200_OK,
    description="Obtain an access and refresh token pair",
    responses=LOGIN_RESPONSES,  # type: ignore
)
@limiter.limit("5/minute")
async def login_user(
    request: Request,
    login_data: UserLoginModel,
    session: AsyncSession = Depends(get_session),
    redis: RedisService = Depends(get_redis),
    
):
    user = await _user_service.get_user_by_email(login_data.email, session)

    # Guard: invalid credentials (deliberately vague error message)
    if (
        user is None
        or user.hashed_password is None
        or not verify_password(login_data.password, user.hashed_password)
    ):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "status": "failure",
                "message": "No active account found with the given credentials",
                "err_code": "unauthorized",
            },
        )

    if not user.is_active:
        raise UserNotActive()
    if not user.is_email_verified:
        raise AccountNotVerified()

    user_payload = {
        "username": user.username,
        "user_id": str(user.id),
        "role": user.role.value,
    }
    tokens = await _user_service.create_token_pair(user_payload, session, redis)

    return {"status": "success", "message": "Login successful", **tokens}


@router.post(
    "/token/refresh",
    status_code=status.HTTP_200_OK,
    description="Refresh an expired access token using a valid refresh token",
    responses=REFRESH_TOKEN_RESPONSES,  # type: ignore
    
)
async def refresh_token(
    redis: RedisService = Depends(get_redis),
    session: AsyncSession = Depends(get_session),
    token_details: dict = Depends(RefreshTokenBearer()),
):
    old_jti = token_details["jti"]
    user_id = token_details["user"]["user_id"]

    # Rotate: revoke old JTI before issuing a new pair
    await redis.remove_jti_from_user_sessions(user_id=user_id, jti=old_jti)
    tokens = await _user_service.create_token_pair(token_details["user"], session, redis)

    return {"status": "success", "message": "Token refreshed successfully", **tokens}


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    responses=LOGOUT_RESPONSES,  # type: ignore
)
async def logout(
    token_details: dict = Depends(RefreshTokenBearer()),
    session: AsyncSession = Depends(get_session),
    redis: RedisService = Depends(get_redis),
):
    await _user_service.revoke_token(
        user_id=token_details["user"]["user_id"],
        jti=token_details["jti"],
        redis=redis
    )
    return {"status": "success", "message": "Logged out successfully"}


@router.post(
    "/logout/all",
    status_code=status.HTTP_200_OK,
    responses=LOGOUT_ALL_RESPONSES,  # type: ignore
)
async def logout_all(
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis: RedisService = Depends(get_redis),
):
    await _user_service.revoke_all_tokens(user_id=str(user.id), redis=redis)
    return {"status": "success", "message": "Logged out of all devices successfully."}


# Password management

@router.post(
    "/password/reset",
    status_code=status.HTTP_200_OK,
    responses=PASSWORD_RESET_REQUEST_RESPONSES,  # type: ignore
)
async def password_reset_request(
    email_data: PasswordResetModel,
    background_tasks: BackgroundTasks,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    # Always return the same message to avoid user-enumeration attacks
    _GENERIC_RESPONSE = {
        "status": "success",
        "message": (
            "If that email address is in our database, "
            "we will send you an email to reset your password."
        ),
    }

    user = await _user_service.get_user_by_email(email_data.email, session)
    if not user or not user.is_active:
        logging.warning(
            "Password reset attempt on invalid/inactive account",
            extra={
                "event_type": "password_reset_invalid_email",
                "email": email_data.email,
                "user_agent": request.headers.get("user-agent"),
            },
        )
        return _GENERIC_RESPONSE

    otp = await _user_service.generate_otp(user, session)
    send_email_by_type(
        background_tasks, "reset", user.email, user.first_name, otp=str(otp)
    )
    return _GENERIC_RESPONSE


@router.post(
    "/password/reset/otp-verify",
    status_code=status.HTTP_200_OK,
    responses=PASSWORD_RESET_VERIFY_RESPONSES,  # type: ignore
)
@limiter.limit("5/minute")
async def password_reset_verify_otp(
    request: Request,
    data: PasswordResetVerifyOtpModel,
    session: AsyncSession = Depends(get_session),
):
    user = await _user_service.get_user_by_email(data.email, session)
    if not user:
        raise NotFound("User not found")
    if not user.is_active:
        raise UserNotActive()

    otp_record = await _user_service.get_otp_by_user(str(user.id), data.otp, session)
    if not otp_record or not otp_record.is_valid:
        raise InvalidOtp()

    await _user_service.invalidate_otps(user, session)

    return {"status": "success", "message": "OTP verified. Proceed to set a new password."}


@router.post(
    "/password/reset/complete",
    status_code=status.HTTP_200_OK,
    responses=PASSWORD_RESET_COMPLETE_RESPONSES,  # type: ignore
)
async def password_reset_done(
    data: PasswordResetConfirmModel,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    user = await _user_service.get_user_by_email(data.email, session)
    if not user:
        raise NotFound("User not found")
    if not user.is_active:
        raise UserNotActive()

    await _user_service.update_user(
        user, {"hashed_password": hash_password(data.new_password)}, session
    )
    send_email_by_type(background_tasks, "reset-success", user.email, user.first_name)

    return {"status": "success", "message": "Password reset. Proceed to login"}


@router.post(
    "/password/change",
    status_code=status.HTTP_200_OK,
    responses=PASSWORD_CHANGE_RESPONSES,  # type: ignore
)
async def password_change(
    data: PasswordChangeModel,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis: RedisService = Depends(get_redis),
):
    if data.new_password != data.confirm_new_password:
        raise PasswordMismatch()

    user = await _user_service.get_user_by_email(current_user.email, session)

    if not verify_password(data.old_password, user.hashed_password): # type: ignore
        raise InvalidOldPassword()
    if verify_password(data.new_password, user.hashed_password):  # type: ignore
        raise PasswordSameAsOld()

    await _user_service.update_user(
        user, {"hashed_password": hash_password(data.new_password)}, session
    ) if user else None

    # Invalidate all sessions after a password change, then issue fresh tokens
    await _user_service.revoke_all_tokens(user_id=str(user.id), redis=redis) if user else None
    user_payload = {"email": user.email, "user_id": str(user.id), "role": user.role.value} if user else None
    tokens = await _user_service.create_token_pair(user_payload, session, redis=redis) if user_payload else None

    return {"status": "success", "message": "Password changed successfully.", **tokens} # type: ignore # TODO: USE HTTP-COOKIE LATER



# Google OAuth

@router.get(
    "/google",
    status_code=status.HTTP_302_FOUND,
    description="""
**Google OAuth Authentication**

Initiates the Google OAuth flow. This endpoint performs a browser redirect —
it will not work correctly in Swagger UI. To test:

1. Copy the full URL: `http://127.0.0.1:8000/api/v1/auth/google`
2. Paste it directly into your browser's address bar
3. After authenticating, you will be redirected back to the callback URL
    """,
    responses={302: {"description": "Redirect to Google OAuth authorization page"}},
)
async def google_auth(request: Request):
    return await oauth.google.authorize_redirect(request, auth_settings.GOOGLE_REDIRECT_URI)


@router.get("/google/callback", include_in_schema=False)
async def google_auth_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    redis: RedisService = Depends(get_redis),
):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        email = user_info.get("email")
        AUTH_PROVIDER = "google"

        existing_user = await _user_service.get_user_by_email(email, session)

        if existing_user and existing_user.auth_provider == AUTH_PROVIDER:
            # Returning OAuth user — log them in
            tokens = await _user_service.handle_oauth_login(existing_user, session, redis=redis)
            redirect_url = (
                f"{Config.FRONTEND_CALLBACK_URL}"
                f"?access={tokens['access']}&refresh={tokens['refresh']}&is_new=false"
            )
            return RedirectResponse(redirect_url)

        # New OAuth user — register them
        user_create_obj = UserCreateOAuth(
            first_name=user_info.get("given_name"),
            last_name=user_info.get("family_name"),
            username=email.split("@")[0],
            email=email,
            google_id=user_info.get("sub"),
            auth_provider=AUTH_PROVIDER,
        )

        new_user, tokens = await _user_service.handle_oauth_register(
            user_create_obj, session, redis
        )

        send_email_by_type(
            background_tasks, "welcome", new_user.email, new_user.first_name
        )

        if picture_url := user_info.get("picture"):
            background_tasks.add_task(
                upload_profile_picture_task,
                user_id=str(new_user.id),
                image_url=picture_url,
            )

        redirect_url = (
            f"{Config.FRONTEND_CALLBACK_URL}"
            f"?access={tokens['access']}&refresh={tokens['refresh']}&is_new=true"
        )
        return RedirectResponse(redirect_url)

    except Exception as e:
        logging.exception(f"Google authentication failed: {e}")
        raise GoogleAuthenticationFailed()