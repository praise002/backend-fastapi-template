import logging
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from src.config import Config

password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(user_data: dict, expires_delta: timedelta | None = None):
    if expires_delta:
        duration = expires_delta
    else:
        duration = timedelta(minutes=Config.ACCESS_TOKEN_EXPIRY)

    now = datetime.now(timezone.utc)
    expiry = now + duration

    payload = {
        "token_type": "access",
        "exp": expiry,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "user": user_data,
    }

    token = jwt.encode(
        payload=payload, key=Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM
    )

    return token


def create_refresh_token(user_data: dict, expiry: timedelta | None = None):
    if expiry is None:
        expiry = timedelta(days=Config.REFRESH_TOKEN_EXPIRY)

    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())

    payload = {
        "token_type": "refresh",
        "exp": now + expiry,
        "iat": now,  # issued at in unix timestamp
        "jti": jti,
        "user": user_data,
    }  # user_id, full_name

    token = jwt.encode(
        payload=payload, key=Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM
    )

    return token


def decode_token(token: str) -> dict | None:
    try:
        token_data = jwt.decode(
            jwt=token, key=Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM]
        )
        return token_data
    except jwt.PyJWTError as e:
        logging.exception(e)
        return None
