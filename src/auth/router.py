import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.background_tasks import upload_profile_picture_task
from src.auth.dependencies import RefreshTokenBearer, RoleChecker, get_current_user
from src.auth.oauth_config import oauth
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
from src.auth.utils import generate_otp, invalidate_previous_otps
from src.config import Config
from src.db.main import get_session
from src.db.redis import remove_jti_from_user_sessions
from src.errors import (
    AccountNotVerified,
    GoogleAuthenticationFailed,
    InvalidOldPassword,
    InvalidOtp,
    NotFound,
    PasswordMismatch,
    PasswordSameAsOld,
    UserAlreadyExists,
    UsernameAlreadyExists,
    UserNotActive,
)
from src.limiter import limiter
from src.mail import send_email_by_type

router = APIRouter()

user_service = UserService()
role_checker = RoleChecker(["admin", "user"])
REFRESH_TOKEN = Config.REFRESH_TOKEN_EXPIRY


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserRegistrationResponse,
    description="This endpoint registers new users into our application",
    responses=REGISTER_RESPONSES,  # type: ignore
)
@limiter.limit("5/minute")
async def create_user_account(
    request: Request,
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    email = user_data.email
    user_exists = await user_service.user_exists(email, session)
    if user_exists:
        raise UserAlreadyExists()

    username = user_data.username
    username_exists = await user_service.username_exists(username, session)
    if username_exists:
        raise UsernameAlreadyExists()

    new_user = await user_service.create_user(user_data, session)

    otp = await generate_otp(new_user, session)
    send_email_by_type(
        background_tasks,
        "activate",
        new_user.email,
        new_user.first_name,
        otp=otp,
    )
    # send_email(
    #     background_tasks,
    #     "Verify your email",
    #     new_user.email,
    #     {"name": new_user.first_name, "otp": str(otp)},
    #     "verify_email_request.html",
    # )

    return {
        "status": "success",
        "message": "Account Created! Check email to verify your account",
        "email": new_user.email,
    }


@router.post(
    "/account-verification",
    status_code=status.HTTP_200_OK,
    description="This endpoint verifies a user's email",
    responses=VERIFY_EMAIL_RESPONSES,  # type: ignore
)
@limiter.limit("5/minute")
async def verify_user_account(
    request: Request,
    data: OtpVerify,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):

    email = data.email
    otp = data.otp

    user = await user_service.get_user_by_email(email, session)

    if not user:
        raise NotFound("User not found")

    user_id = user.id
    otp_record = await user_service.get_otp_by_user(user_id, otp, session)

    if not otp_record or not otp_record.is_valid:
        raise InvalidOtp()

    if user.is_email_verified:
        return {
            "status": "success",
            "message": "Email address already verified.",
        }

    await user_service.update_user(user, {"is_email_verified": True}, session)

    await invalidate_previous_otps(user, session)

    send_email_by_type(
        background_tasks,
        "welcome",
        user.email,
        user.first_name,
    )

    return {
        "status": "success",
        "message": "Email verified successfully",
    }


@router.post(
    "/verification/email-resend",
    status_code=status.HTTP_200_OK,
    description="This endpoint sends OTP to a user's email for verification",
    responses=RESEND_OTP_RESPONSES,  # type: ignore
)
async def resend_verification_email(
    data: SendOtp,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    email = data.email
    user = await user_service.get_user_by_email(email, session)

    if not user:
        raise NotFound("User not found")

    if user.is_email_verified:
        return {
            "status": "success",
            "message": "Email address already verified. No OTP sent",
        }

    await invalidate_previous_otps(user, session)

    otp = await generate_otp(user, session)
    send_email_by_type(
        background_tasks,
        "activate",
        user.email,
        user.first_name,
        otp=otp,
    )

    return {
        "status": "success",
        "message": "OTP sent successfully",
    }


@router.post(
    "/token",
    status_code=status.HTTP_200_OK,
    description="This endpoint generates new access and refresh tokens for authentication",
    responses=LOGIN_RESPONSES,  # type: ignore
)
@limiter.limit("5/minute")
async def login_user(
    request: Request,
    login_data: UserLoginModel, session: AsyncSession = Depends(get_session)
):
    email = login_data.email
    password = login_data.password

    user = await user_service.get_user_by_email(email, session)

    if (
        user is None
        or user.hashed_password is None
        or not verify_password(password, user.hashed_password)
    ):
        return JSONResponse(
            content={
                "status": "failure",
                "message": "No active account found with the given credentials",
                "err_code": "unauthorized",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise UserNotActive()

    if not user.is_email_verified:
        raise AccountNotVerified()

    password_valid = verify_password(password, user.hashed_password)
    if password_valid:
        user_data = user_data = {
            "username": user.username,
            "user_id": str(user.id),
            "role": user.role.value,
        }
        tokens = await user_service.create_token_pair(user_data, session)

        return {
            "status": "success",
            "message": "Login successful",
            **tokens,
        }  # TODO: USE HTTP-COOKIE LATER


@router.post(
    "/token/refresh",
    status_code=status.HTTP_200_OK,
    description="This endpoint allows users to refresh their access token using a valid refresh token. It returns a new access and refresh token, which can be used for further authenticated requests.",
    responses=REFRESH_TOKEN_RESPONSES,  # type: ignore
)
async def refresh_token(
    session: AsyncSession = Depends(get_session),
    token_details: dict = Depends(RefreshTokenBearer()),
):
    old_jti = token_details["jti"]
    user_id = token_details["user"]["user_id"]

    await remove_jti_from_user_sessions(user_id=user_id, jti=old_jti)

    # Create new token pair (automatically adds new JTI to Redis)
    new_token = await user_service.create_token_pair(token_details["user"], session)

    return {
        "status": "success",
        "message": "Token refreshed successfully",
        **new_token,
    }


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    responses=LOGOUT_RESPONSES,  # type: ignore
)
async def logout(
    token_details: dict = Depends(RefreshTokenBearer()),
    session: AsyncSession = Depends(get_session),
):
    jti = token_details["jti"]
    user_id = token_details["user"]["user_id"]
    # Remove this specific JTI from user's sessions
    await user_service.revoke_user_token(user_id=user_id, jti=jti)
    return {"status": "success", "message": "Logged Out Successfully"}


@router.post(
    "/logout/all",
    status_code=status.HTTP_200_OK,
    responses=LOGOUT_ALL_RESPONSES,  # type: ignore
)
async def logout_all(
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Delete entire Redis Set for this user
    await user_service.revoke_all_user_tokens(user_id=str(user.id))
    return {"status": "success", "message": "Logged out of all devices successfully"}


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
    email = email_data.email
    user = await user_service.get_user_by_email(email, session)
    if not user or not user.is_active:
        # silently pass due to security reasons
        logging.warning(
            "Password reset attempt on invalid/inactive account",
            extra={
                "event_type": "password_reset_invalid_email",
                "email": email,
                "user_agent": request.headers.get("user-agent"),
            },
        )
        return {
            "status": "success",
            "message": "If that email address is in our database, we will send you an email to reset your password",
        }

    otp = await generate_otp(user, session)
    send_email_by_type(
        background_tasks,
        "reset",
        user.email,
        user.first_name,
        otp=otp,
    )

    # ALWAYS return the same message
    return {
        "status": "success",
        "message": "If that email address is in our database, we will send you an email to reset your password",
    }


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
    email = data.email
    otp = data.otp

    user = await user_service.get_user_by_email(email, session)

    if not user:
        raise NotFound("User not found")

    if not user.is_active:
        raise UserNotActive()

    user_id = user.id
    otp_record = await user_service.get_otp_by_user(user_id, otp, session)

    if not otp_record or not otp_record.is_valid:
        raise InvalidOtp()

    # Clear OTP after verification
    await invalidate_previous_otps(user, session)

    return {
        "status": "success",
        "message": "OTP verified, proceed to set a new password",
    }


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
    email = data.email
    new_password = data.new_password

    user = await user_service.get_user_by_email(email, session)

    if not user:
        raise NotFound("User not found")

    if not user.is_active:
        raise UserNotActive()

    passwd_hash = hash_password(new_password)
    await user_service.update_user(user, {"hashed_password": passwd_hash}, session)
    send_email_by_type(
        background_tasks,
        "reset-success",
        user.email,
        user.first_name,
    )

    return {
        "status": "success",
        "message": "Your password has been reset, proceed to login",
    }


@router.post(
    "/password/change",
    status_code=status.HTTP_200_OK,
    responses=PASSWORD_CHANGE_RESPONSES,  # type: ignore
)
async def password_change(
    data: PasswordChangeModel,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if data.new_password != data.confirm_new_password:
        raise PasswordMismatch()

    user = await user_service.get_user_by_email(current_user.email, session)

    if not verify_password(data.old_password, user.hashed_password):
        raise InvalidOldPassword()

    if verify_password(data.new_password, user.hashed_password):
        raise PasswordSameAsOld()

    hashed_password = hash_password(data.new_password)
    await user_service.update_user(user, {"hashed_password": hashed_password}, session)

    # Invalidate all sessions after password change
    await user_service.revoke_all_user_tokens(user_id=str(user.id))

    user_data = {
        "email": user.email,
        "user_id": str(user.id),
        "role": user.role.value,
    }
    tokens = await user_service.create_token_pair(user_data, session)

    return {
        "status": "success",
        "message": "Password changed successfully",
        **tokens,
    }  # TODO: USE HTTP-COOKIE LATER


@router.get(
    "/google",
    status_code=status.HTTP_302_FOUND,
    description="""
    **Google OAuth Authentication**
    
    This endpoint initiates Google OAuth authentication flow.
    
    Important for API Documentation Users:
    - This endpoint performs a redirect to Google's authentication page
    - Redirects do not work properly in Swagger UI/API documentation
    - To test this endpoint:
      1. Copy the full URL: `http://127.0.0.1:8000/api/v1/auth/google`
      2. Paste it directly into your browser address bar
      3. You will be redirected to Google for authentication
      4. After authentication, you'll be redirected back to the callback URL
    """,
    responses={302: {"description": "Redirect to Google OAuth authorization page"}},
)
async def google_auth(request: Request):
    """Redirect user to Google for authorization"""
    redirect_url = Config.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_url)


@router.get("/google/callback", include_in_schema=False)
async def google_auth_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Handle Google OAuth callback - this is where you get tokens"""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        email = user_info.get("email")
        AUTH_PROVIDER = "google"

        existing_user = await user_service.get_user_by_email(email, session)

        if existing_user and existing_user.auth_provider == AUTH_PROVIDER:
            tokens = await user_service.handle_oauth_user_login(existing_user, session)

            access = tokens["access"]
            refresh = tokens["refresh"]

            frontend_callback_url = Config.FRONTEND_CALLBACK_URL
            redirect_url = (
                f"{frontend_callback_url}"
                f"?access={access}&refresh={refresh}&is_new=true"
            )
            return RedirectResponse(redirect_url)

        else:
            first_name = user_info.get("given_name")
            last_name = user_info.get("family_name")
            picture_url = user_info.get("picture")
            auth_provider = user_info.get("iss")
            print(auth_provider)
            google_id = user_info.get("sub")
            username = email.split("@")[0]
            user_create_obj = UserCreateOAuth(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                google_id=google_id,
                auth_provider=AUTH_PROVIDER,
            )

            new_user, response = await user_service.handle_oauth_user_register(
                user_create_obj, session
            )

            send_email_by_type(
                background_tasks,
                "welcome",
                new_user.email,
                new_user.first_name,
            )

            # Upload profile picture in background
            if picture_url:
                background_tasks.add_task(
                    upload_profile_picture_task,
                    user_id=str(new_user.id),
                    image_url=picture_url,
                )

                logging.info(
                    "Profile picture upload task queued for new user",
                    extra={
                        "event_type": "profile_picture_task_queued",
                        "user_id": str(new_user.id),
                        "email": email,
                    },
                )

            return response

    except Exception as e:
        logging.exception(f"Google authentication failed: {str(e)}")
        raise GoogleAuthenticationFailed()
