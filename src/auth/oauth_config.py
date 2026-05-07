from authlib.integrations.starlette_client import OAuth

from src.auth.config import auth_settings

oauth = OAuth()
oauth.register(
    name="google",
    client_id=auth_settings.GOOGLE_CLIENT_ID,
    client_secret=auth_settings.GOOGLE_CLIENT_SECRET,
    redirect_uri=auth_settings.GOOGLE_REDIRECT_URI,
    client_kwargs={
        "scope": "openid email profile",
    },
    authorize_params={
        "access_type": "offline",  # Get refresh tokens
        "prompt": "select_account",
    },
    server_metadata_url="https://accounts.google.com/.well-known/openid-auth_settingsuration",
)