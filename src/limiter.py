from slowapi import Limiter
from slowapi.util import get_remote_address

# from src.config import Config

# limiter = Limiter(key_func=get_remote_address, enabled=Config.ENVIRONMENT != "test")
limiter = Limiter(key_func=get_remote_address)