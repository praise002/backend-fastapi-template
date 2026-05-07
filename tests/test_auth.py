import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from auth.redis import RedisService
from src.auth.service import UserService
from src.db.models import Otp, User


class TestUserRegistration:
    register_url = "/api/v1/auth/register"

    """Test suite for user registration endpoint."""

    async def test_register_user_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        valid_user_data: dict,
        mock_email: list,
    ):
        # Act: Make registration request
        response = await async_client.post(self.register_url, json=valid_user_data)
        print(response.json())
        # Assert: Check response
        assert response.status_code == 201
        response_data = response.json()

        assert response_data["status"] == "success"
        assert "verify" in response_data["message"]
        assert response_data["email"] == valid_user_data["email"]

        # Assert: Check database
        user_service = UserService()
        user = await user_service.get_user_by_email(
            valid_user_data["email"], db_session
        )

        assert user is not None
        assert user.email == valid_user_data["email"]
        assert user.username == valid_user_data["username"]
        assert user.first_name == valid_user_data["first_name"]
        assert user.last_name == valid_user_data["last_name"]
        assert not user.is_email_verified
        assert user.is_active

        # Assert: Check email was sent
        assert len(mock_email) == 1
        email_data = mock_email[0]
        assert email_data["email_to"] == valid_user_data["email"]
        assert email_data["subject"] == "Verify your email"
        assert "otp" in email_data["template_context"]
        assert email_data["template_name"] == "verify_email_request.mjml"

    async def test_register_very_long_password(
        self,
        async_client: AsyncClient,
        valid_user_data: dict,
    ):
        valid_data = valid_user_data.copy()
        valid_data["password"] = "A" * 1000

        response = await async_client.post(self.register_url, json=valid_data)
        print(response.json())

        assert response.status_code == 422

    async def test_register_user_already_exists(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        valid_user_data: dict,
        mock_email: list,
    ):
        # Arrange
        await async_client.post(self.register_url, json=valid_user_data)
        duplicate_request = valid_user_data.copy()
        duplicate_request["username"] = "different_username_123"

        # Act: Try to register same user again
        response = await async_client.post(self.register_url, json=duplicate_request)

        # Assert
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "user_exists"

    async def test_register_username_already_exists(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        valid_user_data: dict,
        mock_email: list,
    ):
        """
        Test registration fails when username already exists.
        """
        # Arrange
        await async_client.post(self.register_url, json=valid_user_data)
        duplicate_request = valid_user_data.copy()
        duplicate_request["email"] = "email@email.com"

        # Act: Try to register with duplicate username
        response = await async_client.post(self.register_url, json=duplicate_request)

        # Assert
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "username_exists"

    async def test_register_invalid_email(
        self,
        async_client: AsyncClient,
        invalid_user_data: dict,
    ):
        """
        Test registration fails with invalid email format.
        """

        response = await async_client.post(self.register_url, json=invalid_user_data)

        assert response.status_code == 422

    async def test_register_weak_password(
        self,
        async_client: AsyncClient,
        weak_password_data: dict,
    ):
        """
        Test registration fails with weak password.
        """

        response = await async_client.post(self.register_url, json=weak_password_data)

        assert response.status_code == 422

    async def test_register_missing_required_fields(
        self,
        async_client: AsyncClient,
    ):
        """
        Test registration fails when required fields are missing.
        """
        incomplete_data = {
            "email": "test@example.com",
        }

        response = await async_client.post(self.register_url, json=incomplete_data)

        assert response.status_code == 422

    async def test_password_is_hashed(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        mock_email: list,
        another_user_data: dict,
    ):
        """
        Test that password is properly hashed in database.
        """
        # Act
        response = await async_client.post(self.register_url, json=another_user_data)

        # Assert
        assert response.status_code == 201

        # Check password is hashed (not stored in plain text)
        user_service = UserService()
        user = await user_service.get_user_by_email(
            another_user_data["email"], db_session
        )

        assert user.hashed_password is not None # type: ignore
        assert user.hashed_password != another_user_data["password"] # type: ignore
        assert len(user.hashed_password) > 20 # type: ignore


class TestEmailVerification:
    """Test suite for email verification endpoint."""

    verify_user_email = "/api/v1/auth/account-verification"

    async def test_verify_email_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        registered_user: User,
        otp_for_user: int,
        mock_email: list,
    ):

        # Arrange
        verification_data = {"email": registered_user.email, "otp": otp_for_user}

        # Act: Verify email
        response = await async_client.post(
            self.verify_user_email, json=verification_data
        )

        # Assert: Check response
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "success"
        assert "verified" in response_data["message"]

        # Assert: Check user is verified in database
        user_service = UserService()
        
        updated_user = await user_service.get_user_by_email(
            registered_user.email, db_session
        )
        print(updated_user)
        await db_session.refresh(updated_user)

        assert updated_user.is_email_verified is True  # type: ignore
        

        # Assert: Check OTP is invalidated
        otp_record = await user_service.get_otp_by_user(
            str(registered_user.id), otp_for_user, db_session
        )
        assert otp_record is None

        # Assert: Check welcome email was sent
        assert len(mock_email) == 1

        email_data = mock_email[0]
        assert email_data["template_name"] == "welcome_message.mjml"

    async def test_verify_email_invalid_otp(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        registered_user: User,
    ):
        """
        Test verification fails with invalid OTP.
        """
        # Arrange
        verification_data = {
            "email": registered_user.email,
            "otp": "999999",
        }

        # Act
        response = await async_client.post(
            self.verify_user_email, json=verification_data
        )

        # Assert
        assert response.status_code == 422
        response_data = response.json()
        assert response_data["err_code"] == "invalid_otp"

        # Assert: User should still be unverified
        user_service = UserService()
        user = await user_service.get_user_by_email(registered_user.email, db_session)
        assert user.is_email_verified is False  # type: ignore

    async def test_verify_email_user_not_found(
        self,
        async_client: AsyncClient,
        otp_for_user: str,
    ):
        """
        Test verification fails for non-existent user.
        """
        # Arrange
        verification_data = {"email": "nonexistent@example.com", "otp": otp_for_user}

        # Act
        response = await async_client.post(
            self.verify_user_email, json=verification_data
        )

        # Assert
        assert response.status_code == 404

    async def test_verify_email_already_verified(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
        mock_email: list,
    ):
        """
        Test verification when user is already verified.
        """
        # Arrange
        otp_record = Otp(user_id=verified_user.id, otp=123456)  # type: ignore
        db_session.add(otp_record)
        await db_session.commit()

        verification_data = {"email": verified_user.email, "otp": 123456}

        # Act
        response = await async_client.post(
            self.verify_user_email, json=verification_data
        )

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "success"
        assert response_data["message"] == "Email address already verified."

        # Assert: No welcome emails should be sent for already verified users
        assert len(mock_email) == 0

    async def test_verify_email_missing_fields(
        self,
        async_client: AsyncClient,
        registered_user: User,
        otp_for_user: str,
    ):
        """
        Test verification fails when required fields are missing.
        """
        # Test missing email
        response = await async_client.post(
            self.verify_user_email, json={"otp": otp_for_user}
        )
        assert response.status_code == 422

        # Test missing OTP
        response = await async_client.post(
            self.verify_user_email, json={"email": registered_user.email}
        )
        assert response.status_code == 422

        # Test empty data
        response = await async_client.post(self.verify_user_email, json={})
        assert response.status_code == 422

    async def test_verify_email_invalid_otp_format(
        self,
        async_client: AsyncClient,
        registered_user: User,
    ):
        """
        Test verification fails with invalid OTP formats.
        """
        invalid_otp_cases = [
            "12345",  # Too short
            "1234567",  # Too long
            "abcdef",  # Non-numeric
            "12 3456",  # Contains space
            "",  # Empty
        ]

        for invalid_otp in invalid_otp_cases:
            verification_data = {"email": registered_user.email, "otp": invalid_otp}

            response = await async_client.post(
                self.verify_user_email, json=verification_data
            )
            print(response.json())

            # Should either be validation error or invalid OTP error
            assert response.status_code == 422


class TestResendVerificationEmail:
    """Test suite for OTP resend endpoint."""

    resend_verification = "/api/v1/auth/verification/email-resend"

    @pytest.mark.asyncio
    async def test_resend_otp_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        registered_user: User,
        mock_email: list,
    ):
        # Arrange
        resend_data = {"email": registered_user.email}

        # Create some existing OTPs to test invalidation
        existing_otp = Otp(user_id=registered_user.id, otp=123456) # type: ignore
        db_session.add(existing_otp)
        await db_session.commit()

        # Act: Resend verification email
        response = await async_client.post(self.resend_verification, json=resend_data)

        # Assert: Check response
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "success"
        assert response_data["message"] == "OTP sent successfully"

        # Assert: Check email was sent
        assert len(mock_email) == 1
        email_data = mock_email[0]
        assert email_data["template_name"] == "verify_email_request.mjml"

        user_service = UserService()
        # Assert: There should be exactly ONE new OTP for the user
        all_otps = await user_service.get_user_otps(str(registered_user.id), db_session)
        print(all_otps)
        assert len(all_otps) == 1

    async def test_resend_otp_user_not_found(
        self,
        async_client: AsyncClient,
    ):

        # Arrange
        resend_data = {"email": "nonexistent@example.com"}

        # Act
        response = await async_client.post(self.resend_verification, json=resend_data)

        # Assert
        assert response.status_code == 404
        response_data = response.json()
        assert response_data["err_code"] == "not_found"

    async def test_resend_otp_already_verified(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
        mock_email: list,
    ):
        # Arrange
        resend_data = {"email": verified_user.email}

        # Act
        response = await async_client.post(self.resend_verification, json=resend_data)

        # Assert: Check response
        assert response.status_code == 200
        response_data = response.json()

        assert response_data["status"] == "success"
        assert "Email address already verified" in response_data["message"]

        # Assert: No email should be sent for already verified users
        assert len(mock_email) == 0

    async def test_resend_otp_missing_email(
        self,
        async_client: AsyncClient,
    ):
        # Arrange: Missing email
        resend_data = {}

        # Act
        response = await async_client.post(self.resend_verification, json=resend_data)
        print(response.json())
        # Assert
        assert response.status_code == 422

class TestUserLogin:
    """Test suite for user login endpoint."""

    login_url = "/api/v1/auth/token"

    async def test_login_success(
        self,
        async_client,
        db_session,
        verified_user: User,
        user3_data: dict,        # ← matches verified_user
    ):
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }

        response = await async_client.post(self.login_url, json=login_data)

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["status"] == "success"
        assert response_data["message"] == "Login successful"
        assert "access" in response_data
        assert "refresh" in response_data

        # Assert: Tokens should not be empty
        assert response_data["access"] is not None
        assert response_data["refresh"] is not None

    async def test_login_user_not_found(
        self,
        async_client: AsyncClient,
    ):

        login_data = {
            "email": "nonexistent@example.com",
            "password": "SomePassword123!",
        }

        response = await async_client.post(self.login_url, json=login_data)

        assert response.status_code == 401
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "failure"
        assert response_data["err_code"] == "unauthorized"

    async def test_login_invalid_password(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
    ):

        login_data = {"email": verified_user.email, "password": "WrongPassword123!"}

        response = await async_client.post(self.login_url, json=login_data)

        assert response.status_code == 401
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "failure"
        assert response_data["err_code"] == "unauthorized"

    async def test_login_account_not_verified(
        self,
        async_client,
        db_session,
        registered_user: User,
        user2_data: dict,        
    ):
        login_data = {
            "email": registered_user.email,
            "password": user2_data["password"],
        }
        response = await async_client.post(self.login_url, json=login_data)
        assert response.status_code == 403
        response_data = response.json()
        assert response_data["err_code"] == "account_not_verified"

    async def test_login_user_inactive(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        inactive_user: User,
        another_user_data: dict,
    ):
        login_data = {
            "email": another_user_data["email"],
            "password": another_user_data["password"],
        }

        response = await async_client.post(self.login_url, json=login_data)

        assert response.status_code == 403
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "forbidden"

    async def test_login_missing_email(
        self,
        async_client: AsyncClient,
    ):

        login_data = {"password": "SomePassword123!"}

        response = await async_client.post(self.login_url, json=login_data)
        print(response.json())

        assert response.status_code == 422

    async def test_login_missing_password(
        self,
        async_client: AsyncClient,
        verified_user: User,
    ):

        login_data = {"email": verified_user.email}

        response = await async_client.post(self.login_url, json=login_data)

        assert response.status_code == 422

    async def test_login_empty_credentials(
        self,
        async_client: AsyncClient,
    ):

        login_data = {"email": "", "password": ""}

        response = await async_client.post(self.login_url, json=login_data)

        assert response.status_code == 422

    async def test_login_case_insensitive_email(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
        valid_user_data: dict,
    ):

        login_data = {
            "email": verified_user.email.upper(),
            "password": valid_user_data["password"],
        }

        response = await async_client.post(self.login_url, json=login_data)
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)
        assert response_data["status"] == "success"
        assert "access" in response_data
        assert "refresh" in response_data


class TestLogout:

    logout_url = "/api/v1/auth/logout"
    login_url = "/api/v1/auth/token"

    async def test_logout_success(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()
        refresh_token = tokens["refresh"]

        response = await async_client.post(
            self.logout_url, headers={"Authorization": f"Bearer {refresh_token}"}
        )

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert "Logged out successfully" in response_data["message"]

        # Try to use the same refresh token again
        retry_response = await async_client.post(
            self.logout_url, headers={"Authorization": f"Bearer {refresh_token}"}
        )
        print(retry_response.json())
        assert retry_response.status_code == 401

    async def test_logout_without_token(
        self,
        async_client: AsyncClient,
    ):
        response = await async_client.post(self.logout_url)
        print(response.json())

        assert response.status_code == 401
        response_data = response.json()
        assert response_data["err_code"] == "unauthorized"

    async def test_logout_with_invalid_token(
        self,
        async_client: AsyncClient,
    ):
        invalid_token = "invalid.token.here"

        response = await async_client.post(
            self.logout_url, headers={"Authorization": f"Bearer {invalid_token}"}
        )
        print(response.json())

        assert response.status_code == 401

    async def test_logout_with_access_token(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()
        access_token = tokens["access"]

        response = await async_client.post(
            self.logout_url, headers={"Authorization": f"Bearer {access_token}"}
        )
        print(response.json())

        assert response.status_code == 401

    async def test_logout_with_expired_token(
        self,
        async_client: AsyncClient,
        expired_refresh_token: str,
    ):

        response = await async_client.post(
            self.logout_url,
            headers={"Authorization": f"Bearer {expired_refresh_token}"},
        )
        response_data = response.json()
        print(response_data)

        assert response.status_code == 401
        assert response_data["err_code"] == "invalid_token"

    async def test_logout_twice_with_same_token(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):

        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()
        refresh_token = tokens["refresh"]

        # First logout
        first_logout = await async_client.post(
            self.logout_url, headers={"Authorization": f"Bearer {refresh_token}"}
        )
        print(first_logout.json())
        assert first_logout.status_code == 200

        # Try to logout again with same token
        second_logout = await async_client.post(
            self.logout_url, headers={"Authorization": f"Bearer {refresh_token}"}
        )
        print(second_logout.json())

        # Second logout should fail
        assert second_logout.status_code == 401


class TestLogoutAll:
    """Test suite for logout all devices endpoint"""

    logout_all_url = "/api/v1/auth/logout/all"
    login_url = "/api/v1/auth/token"

    async def test_logout_all_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
        user3_data: dict,
        redis: RedisService,
    ):
        # Arrange: Create multiple sessions (login multiple times)
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }

        # Session 1
        login1 = await async_client.post(self.login_url, json=login_data)
        tokens1 = login1.json()

        # Session 2
        login2 = await async_client.post(self.login_url, json=login_data)
        tokens2 = login2.json()

        # Session 3
        login3 = await async_client.post(self.login_url, json=login_data)
        tokens3 = login3.json()

        # Act: Logout from all devices using Session 1's access token
        response = await async_client.post(
            self.logout_all_url,
            headers={"Authorization": f"Bearer {tokens1['access']}"},
        )

        # Assert: Check response
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)
        assert response_data["status"] == "success"
        assert "all devices" in response_data["message"].lower()

        # Assert: All refresh tokens should now be blacklisted
        # Try to use refresh token from session 2
        from src.auth.service import UserService

        user_service = UserService()

        # Decode tokens to get JTIs
        from src.auth.security import decode_token

       # Decode tokens to get JTIs
        token1_data = decode_token(tokens1["refresh"])
        token2_data = decode_token(tokens2["refresh"])
        token3_data = decode_token(tokens3["refresh"])

        # Check if decoding succeeded
        assert token1_data is not None, "Failed to decode token 1"
        assert token2_data is not None, "Failed to decode token 2"
        assert token3_data is not None, "Failed to decode token 3"

        refresh1_jti = token1_data["jti"]
        refresh2_jti = token2_data["jti"]
        refresh3_jti = token3_data["jti"]

        user_id = str(verified_user.id)
        
        

        # Check all tokens are blacklisted (i.e., not valid)
        assert not await user_service.is_token_valid(user_id, refresh1_jti, redis)
        assert not await user_service.is_token_valid(user_id, refresh2_jti, redis)
        assert not await user_service.is_token_valid(user_id, refresh3_jti, redis)

    async def test_logout_all_without_token(
        self,
        async_client: AsyncClient,
    ):
        response = await async_client.post(self.logout_all_url)

        assert response.status_code == 401
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "unauthorized"

    async def test_logout_all_with_invalid_token(
        self,
        async_client: AsyncClient,
    ):
        invalid_token = "invalid.token.here"

        response = await async_client.post(
            self.logout_all_url, headers={"Authorization": f"Bearer {invalid_token}"}
        )
        print(response.json())

        assert response.status_code == 401

    async def test_logout_all_with_refresh_token(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }

        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()
        refresh_token = tokens["refresh"]

        # Try to logout all with refresh token (should fail)
        response = await async_client.post(
            self.logout_all_url, headers={"Authorization": f"Bearer {refresh_token}"}
        )

        assert response.status_code == 401
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "access_token_required"


class TestTokenRefresh:
    """Test suite for token refresh endpoint"""

    refresh_url = "/api/v1/auth/token/refresh"
    login_url = "/api/v1/auth/token"
    logout_url = "/api/v1/auth/logout"
    logout_all_url = "/api/v1/auth/logout/all"

    async def test_refresh_token_success(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):

        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        old_tokens = login_response.json()
        old_refresh = old_tokens["refresh"]
        old_access = old_tokens["access"]

        response = await async_client.post(
            self.refresh_url, headers={"Authorization": f"Bearer {old_refresh}"}
        )

        # Assert: Check response
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "success"
        assert "Token refreshed successfully" in response_data["message"]
        assert "access" in response_data
        assert "refresh" in response_data

        # New tokens should be different from old ones
        assert response_data["access"] != old_access
        assert response_data["refresh"] != old_refresh

    async def test_refresh_token_blacklists_old_token(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
        user3_data: dict,
    ):
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        old_tokens = login_response.json()
        old_refresh = old_tokens["refresh"]

        # Refresh once
        await async_client.post(
            self.refresh_url, headers={"Authorization": f"Bearer {old_refresh}"}
        )

        # Try to refresh again with same old token
        retry_response = await async_client.post(
            self.refresh_url, headers={"Authorization": f"Bearer {old_refresh}"}
        )

        # Assert: Should fail because old token is blacklisted
        assert retry_response.status_code == 401
        response_data = retry_response.json()
        print(response_data)
        assert response_data["err_code"] == "invalid_token"

    async def test_refresh_token_without_token(
        self,
        async_client: AsyncClient,
    ):
        response = await async_client.post(self.refresh_url)

        assert response.status_code == 401
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "unauthorized"

    async def test_refresh_with_access_token(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):

        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()
        access_token = tokens["access"]

        # try to refresh with access token
        response = await async_client.post(
            self.refresh_url, headers={"Authorization": f"Bearer {access_token}"}
        )

        # Should fail
        assert response.status_code == 401
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "refresh_token_required"

    async def test_refresh_with_invalid_token(
        self,
        async_client: AsyncClient,
    ):

        invalid_token = "invalid.token.here"

        response = await async_client.post(
            self.refresh_url, headers={"Authorization": f"Bearer {invalid_token}"}
        )

        assert response.status_code == 401
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "invalid_token"

    async def test_refresh_with_expired_token(
        self,
        async_client: AsyncClient,
        expired_refresh_token: str,
    ):

        response = await async_client.post(
            self.refresh_url,
            headers={"Authorization": f"Bearer {expired_refresh_token}"},
        )
        response_data = response.json()
        print(response_data)

        assert response.status_code == 401
        assert response_data["err_code"] == "invalid_token"

    async def test_refresh_after_logout(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()

        # Logout
        await async_client.post(
            self.logout_url, headers={"Authorization": f"Bearer {tokens['refresh']}"}
        )

        # Try to refresh after logout
        response = await async_client.post(
            self.refresh_url, headers={"Authorization": f"Bearer {tokens['refresh']}"}
        )

        # Should fail
        assert response.status_code == 401
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "invalid_token"

    async def test_refresh_after_logout_all(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }

        login1 = await async_client.post(self.login_url, json=login_data)
        tokens1 = login1.json()

        login2 = await async_client.post(self.login_url, json=login_data)
        tokens2 = login2.json()

        # Logout from all devices using session 1

        await async_client.post(
            self.logout_all_url,
            headers={"Authorization": f"Bearer {tokens1['access']}"},
        )

        # Try to refresh tokens from session 2
        response = await async_client.post(
            self.refresh_url, headers={"Authorization": f"Bearer {tokens2['refresh']}"}
        )

        # Should fail because all tokens are blacklisted
        assert response.status_code == 401
        response_data = response.json()
        print(response_data)


class TestPasswordResetRequest:
    """Test suite for password reset request endpoint"""

    reset_url = "/api/v1/auth/password/reset"

    async def test_password_reset_request_success(
        self, async_client: AsyncClient, verified_user: User, mock_email: list
    ):
        reset_data = {"email": verified_user.email}
        response = await async_client.post(self.reset_url, json=reset_data)

        assert response.status_code == 200
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "success"
        assert "If that email address is in our database" in response_data["message"]

        assert len(mock_email) == 1
        email_data = mock_email[0]
        assert email_data["email_to"] == verified_user.email
        assert "otp" in email_data["template_context"]
        print(email_data["template_context"])
        assert email_data["template_name"] == "password_reset_email.mjml"

    async def test_password_reset_request_nonexistent_user(
        self,
        async_client: AsyncClient,
        mock_email: list,
    ):

        reset_data = {"email": "nonexistent@example.com"}

        response = await async_client.post(self.reset_url, json=reset_data)

        # Response looks identical to success case (security measure)
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "success"
        assert "If that email address is in our database" in response_data["message"]

        # Assert: No email was sent (but response doesn't reveal this)
        assert len(mock_email) == 0

    async def test_password_reset_request_unverified_user(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        registered_user: User,
        mock_email: list,
    ):

        reset_data = {"email": registered_user.email}
        print(reset_data)

        response = await async_client.post(self.reset_url, json=reset_data)
        print(response.json())

        # Should succeed (unverified users can reset password)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"

        # Email should be sent
        assert len(mock_email) == 1

    async def test_password_reset_request_inactive_user(
        self,
        async_client: AsyncClient,
        inactive_user: User,
        mock_email: list,
    ):
        """Test password reset request for inactive user"""
        reset_data = {"email": inactive_user.email}

        response = await async_client.post(self.reset_url, json=reset_data)
        print(response.json())

        # Assert: Response is same (doesn't reveal account status)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"

        # email not sent
        assert len(mock_email) == 0

    async def test_password_reset_request_missing_email(
        self,
        async_client: AsyncClient,
    ):

        reset_data = {}

        response = await async_client.post(self.reset_url, json=reset_data)

        # Validation error
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)

    async def test_password_reset_request_case_insensitive_email(
        self,
        async_client: AsyncClient,
        verified_user: User,
        mock_email: list,
    ):

        reset_data = {"email": verified_user.email.upper()}

        response = await async_client.post(self.reset_url, json=reset_data)

        assert response.status_code == 200

        assert len(mock_email) == 1
        assert mock_email[0]["email_to"] == verified_user.email.lower()


class TestPasswordResetVerifyOtp:
    """Test suite for password reset OTP verification endpoint"""

    verify_otp_url = "/api/v1/auth/password/reset/otp-verify"
    reset_request_url = "/api/v1/auth/password/reset"

    async def test_verify_otp_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        registered_user: User,
    ):

        # Create a valid OTP for the user
        otp = 123456
        otp_record = Otp(user_id=registered_user.id, otp=otp)  # type: ignore
        db_session.add(otp_record)
        await db_session.commit()
        print(otp_record)

        # Verify the OTP
        response = await async_client.post(
            self.verify_otp_url,
            json={
                "email": registered_user.email,
                "otp": otp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        print(data)
        assert data["status"] == "success"
        assert "proceed to set a new password" in data["message"].lower()

    async def test_verify_otp_inactive_user(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        inactive_user: User,
    ):

        # Create a valid OTP for the user
        otp = 123456
        otp_record = Otp(user_id=inactive_user.id, otp=otp) # type: ignore
        db_session.add(otp_record)
        await db_session.commit()

        # Verify the OTP
        response = await async_client.post(
            self.verify_otp_url,
            json={
                "email": inactive_user.email,
                "otp": otp,
            },
        )

        # assert response.status_code == 200
        data = response.json()
        print(data)
        assert data["status"] == "failure"
        assert "disabled" in data["message"].lower()

    async def test_verify_otp_user_not_found(
        self,
        async_client: AsyncClient,
    ):
        response = await async_client.post(
            self.verify_otp_url,
            json={
                "email": "nonexistent@example.com",
                "otp": 123456,
            },
        )

        assert response.status_code == 404
        data = response.json()
        print(data)
        assert data["err_code"] == "not_found"

    async def test_verify_otp_no_reset_requested(
        self,
        async_client: AsyncClient,
        verified_user: User,
    ):

        # Act: Try to verify OTP without requesting reset first
        verify_data = {"email": verified_user.email, "otp": 123456}
        response = await async_client.post(self.verify_otp_url, json=verify_data)

        # Assert
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "invalid_otp"

    async def test_verify_otp_expired(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
    ):

        # Arrange: Create an expired OTP (created 15+ minutes ago)
        from datetime import datetime, timedelta, timezone

        expired_otp = Otp(
            user_id=verified_user.id,
            otp=123456,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        )  # type: ignore
        db_session.add(expired_otp)
        await db_session.commit()
        print(expired_otp)

        # Act: Try to verify expired OTP
        verify_data = {"email": verified_user.email, "otp": 123456}
        response = await async_client.post(self.verify_otp_url, json=verify_data)

        # Assert
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "invalid_otp"

    async def test_verify_otp_missing_email(
        self,
        async_client: AsyncClient,
    ):

        # Act: Missing email parameter
        verify_data = {"otp": 123456}
        response = await async_client.post(self.verify_otp_url, json=verify_data)

        # Assert
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)

    async def test_verify_otp_missing_otp(
        self,
        async_client: AsyncClient,
        verified_user: User,
    ):

        # Act: Missing OTP parameter
        verify_data = {"email": verified_user.email}
        response = await async_client.post(self.verify_otp_url, json=verify_data)

        # Assert
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)

    async def test_verify_otp_case_insensitive_email(
        self,
        async_client: AsyncClient,
        verified_user: User,
        db_session: AsyncSession,
    ):
        from datetime import datetime, timezone

        otp = Otp(
            user_id=verified_user.id,
            otp=123456,
            created_at=datetime.now(timezone.utc),
        )  # type: ignore
        db_session.add(otp)
        await db_session.commit()
        print(otp)

        # Act: Verify with uppercase email
        verify_data = {"email": verified_user.email.upper(), "otp": 123456}
        response = await async_client.post(self.verify_otp_url, json=verify_data)

        # Assert: Should succeed
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)
        assert response_data["status"] == "success"


class TestPasswordResetComplete:
    """Test suite for password reset completion endpoint"""

    complete_url = "/api/v1/auth/password/reset/complete"

    async def test_password_reset_complete_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
        mock_email: list,
    ):

        # Arrange: New password data
        new_password_data = {
            "email": verified_user.email,
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }

        # Act: Complete password reset
        response = await async_client.post(self.complete_url, json=new_password_data)

        # Assert: Check response
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "success"
        assert "proceed to login" in response_data["message"].lower()

        user_service = UserService()
        updated_user = await user_service.get_user_by_email(
            verified_user.email, db_session
        )
        await db_session.refresh(updated_user)

        # Verify new password works
        from src.auth.security import verify_password

        assert verify_password("NewSecurePass123!", updated_user.hashed_password)  # type: ignore

        # Assert: Success email was sent
        assert len(mock_email) == 1
        email_data = mock_email[0]
        assert email_data["email_to"] == verified_user.email
        assert email_data["template_name"] == "password_reset_success.mjml"

    async def test_password_reset_complete_user_not_found(
        self,
        async_client: AsyncClient,
    ):

        # Arrange: Non-existent user data
        reset_data = {
            "email": "nonexistent@example.com",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }

        # Act: Try to complete reset
        response = await async_client.post(self.complete_url, json=reset_data)

        # Assert
        assert response.status_code == 404
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "not_found"

    async def test_password_reset_complete_password_mismatch(
        self,
        async_client: AsyncClient,
        verified_user: User,
    ):
        # Arrange: Mismatched passwords
        reset_data = {
            "email": verified_user.email,
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "DifferentPass123!",
        }

        # Act: Try to complete reset
        response = await async_client.post(self.complete_url, json=reset_data)

        # Assert: Should fail validation
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)
        # Pydantic validation error for password mismatch

    async def test_password_reset_complete_weak_password(
        self,
        async_client: AsyncClient,
        verified_user: User,
    ):

        # Arrange: Weak password
        reset_data = {
            "email": verified_user.email,
            "new_password": "123",
            "confirm_new_password": "123",
        }

        # Act: Try to complete reset
        response = await async_client.post(self.complete_url, json=reset_data)

        # Assert: Should fail validation
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)
        # Pydantic validation error for weak password

    async def test_password_reset_complete_missing_fields(
        self,
        async_client: AsyncClient,
        verified_user: User,
    ):

        # Test missing email
        reset_data = {
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }
        response = await async_client.post(self.complete_url, json=reset_data)
        print(response.json())
        assert response.status_code == 422

        # Test missing new_password
        reset_data = {
            "email": verified_user.email,
            "confirm_new_password": "NewSecurePass123!",
        }
        response = await async_client.post(self.complete_url, json=reset_data)
        print(response.json())
        assert response.status_code == 422

        # Test missing confirm_new_password
        reset_data = {
            "email": verified_user.email,
            "new_password": "NewSecurePass123!",
        }
        response = await async_client.post(self.complete_url, json=reset_data)
        print(response.json())
        assert response.status_code == 422

    async def test_password_reset_complete_case_insensitive_email(
        self,
        async_client: AsyncClient,
        verified_user: User,
        mock_email: list,
    ):

        # Arrange: New password data with uppercase email
        reset_data = {
            "email": verified_user.email.upper(),
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }

        # Act: Complete reset
        response = await async_client.post(self.complete_url, json=reset_data)

        # Assert: Should succeed
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)
        assert response_data["status"] == "success"

        # Assert: Email was sent to lowercase email
        assert len(mock_email) == 1
        assert mock_email[0]["email_to"] == verified_user.email.lower()

    async def test_password_reset_complete_inactive_user(
        self,
        async_client: AsyncClient,
        inactive_user: User,
    ):

        # Arrange: Reset data for inactive user
        reset_data = {
            "email": inactive_user.email,
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }

        # Act: Complete reset
        response = await async_client.post(self.complete_url, json=reset_data)

        # Assert: Should succeed (inactive users can reset password)
        assert response.status_code == 403
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "forbidden"

    async def test_password_reset_complete_unverified_user(
        self,
        async_client: AsyncClient,
        registered_user: User,
        mock_email: list,
    ):

        # Arrange: Reset data for unverified user
        reset_data = {
            "email": registered_user.email,
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }

        # Act: Complete reset
        response = await async_client.post(self.complete_url, json=reset_data)

        # Assert: Should succeed (unverified users can reset password)
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)
        assert response_data["status"] == "success"

        # Assert: Success email was sent
        assert len(mock_email) == 1


class TestPasswordChange:
    """Test suite for password change endpoint"""

    change_url = "/api/v1/auth/password/change"
    login_url = "/api/v1/auth/token"

    async def test_password_change_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
        user3_data: dict,
    ):

        # Arrange: Login to get access token
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        assert login_response.status_code == 200
        tokens = login_response.json()
        access_token = tokens["access"]

        # Act: Change password
        change_data = {
            "old_password": user3_data["password"],
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }
        response = await async_client.post(
            self.change_url,
            json=change_data,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        # Assert: Check response
        assert response.status_code == 200
        response_data = response.json()
        print(response_data)

        assert response_data["status"] == "success"
        assert "Password changed successfully" in response_data["message"]
        assert "access" in response_data
        assert "refresh" in response_data

        user_service = UserService()
        updated_user = await user_service.get_user_by_email(
            verified_user.email, db_session
        )
        await db_session.refresh(updated_user)

        # Verify new password works
        from src.auth.security import verify_password

        assert verify_password("NewSecurePass123!", updated_user.hashed_password) # type: ignore

        # Assert: Old password no longer works
        assert not verify_password(user3_data["password"], updated_user.hashed_password)  # type: ignore

    async def test_password_change_wrong_old_password(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):

        # Arrange: Login to get access token
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()
        access_token = tokens["access"]

        # Act: Try to change password with wrong old password
        change_data = {
            "old_password": "WrongOldPassword123!",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }
        response = await async_client.post(
            self.change_url,
            json=change_data,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        # Assert
        assert response.status_code == 401
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "invalid_old_password"

    async def test_password_change_weak_new_password(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):

        # Arrange: Login to get access token
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()
        access_token = tokens["access"]

        # Act: Try to change password with weak new password
        change_data = {
            "old_password": user3_data["password"],
            "new_password": "123",
            "confirm_new_password": "123",
        }
        response = await async_client.post(
            self.change_url,
            json=change_data,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        # Assert: Should fail validation
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)
        # Pydantic validation error for weak password

    async def test_password_change_unauthenticated(
        self,
        async_client: AsyncClient,
    ):
        # Act: Try to change password without token
        change_data = {
            "old_password": "SomePassword123!",
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }
        response = await async_client.post(self.change_url, json=change_data)

        # Assert
        assert response.status_code == 401
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "unauthorized"

    async def test_password_change_old_tokens_blacklisted(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        verified_user: User,
        user3_data: dict,
    ):

        # Arrange: Login to get initial tokens
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        old_tokens = login_response.json()
        old_access = old_tokens["access"]
        old_refresh = old_tokens["refresh"]

        # Act: Change password
        change_data = {
            "old_password": user3_data["password"],
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }
        response = await async_client.post(
            self.change_url,
            json=change_data,
            headers={"Authorization": f"Bearer {old_access}"},
        )
        assert response.status_code == 200

        # Old refresh token should also be blacklisted
        refresh_response = await async_client.post(
            "/api/v1/auth/token/refresh",
            headers={"Authorization": f"Bearer {old_refresh}"},
        )
        print(refresh_response.json())
        assert refresh_response.status_code == 401

    async def test_password_change_same_as_old_password(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):

        # Arrange: Login to get access token
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()
        access_token = tokens["access"]

        # Act: Try to change password to the same value
        change_data = {
            "old_password": user3_data["password"],
            "new_password": user3_data["password"],
            "confirm_new_password": user3_data["password"],
        }
        response = await async_client.post(
            self.change_url,
            json=change_data,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        # Assert: Should not succeed
        assert response.status_code == 422
        response_data = response.json()
        print(response_data)
        assert response_data["err_code"] == "password_same_as_old"

    async def test_password_change_missing_fields(
        self,
        async_client: AsyncClient,
        verified_user: User,
        user3_data: dict,
    ):

        # Arrange: Login to get access token
        login_data = {
            "email": verified_user.email,
            "password": user3_data["password"],
        }
        login_response = await async_client.post(self.login_url, json=login_data)
        tokens = login_response.json()
        access_token = tokens["access"]

        # Test missing old_password
        change_data = {
            "new_password": "NewSecurePass123!",
            "confirm_new_password": "NewSecurePass123!",
        }
        response = await async_client.post(
            self.change_url,
            json=change_data,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        print(response.json())
        assert response.status_code == 422

        # Test missing new_password
        change_data = {
            "old_password": user3_data["password"],
            "confirm_new_password": "NewSecurePass123!",
        }
        response = await async_client.post(
            self.change_url,
            json=change_data,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        print(response.json())
        assert response.status_code == 422

        # Test missing confirm_new_password
        change_data = {
            "old_password": user3_data["password"],
            "new_password": "NewSecurePass123!",
        }
        response = await async_client.post(
            self.change_url,
            json=change_data,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 422


class TestGoogleOAuth:
    """Test suite for Google OAuth endpoints"""

    google_auth_url = "/api/v1/auth/google"
    google_callback_url = "/api/v1/auth/google/callback"


# FastAPI Filters
# FastAPI-Users
# FastAPI-Admin
# pytest src/tests/test_auth.py::TestPasswordResetVerifyOtp::test_verify_otp_inactive_user -v -s
# pytest src/tests/test_auth.py::TestPasswordResetComplete -v -s
# pytest src/tests/test_auth.py::TestUserRegistration::test_register_user_success -v -s
