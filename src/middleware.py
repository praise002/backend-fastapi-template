import logging
import time

from decouple import config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

# # Set all CORS enabled origins
# if settings.all_cors_origins:
#     app.add_middleware(
#         CORSMiddleware,
#         allow_origins=settings.all_cors_origins,
#         allow_credentials=True,
#         allow_methods=["*"],
#         allow_headers=["*"],
#     )
def register_middleware(app: FastAPI):
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log each HTTP request/response"""
        start_time = time.perf_counter()

        logging.info(
            "Incoming request",
            extra={
                "event_type": "http_request",
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host,  # type: ignore
            },
        )

        response = await call_next(request)

        duration = time.perf_counter() - start_time

        logging.info(
            "Request completed",
            extra={
                "event_type": "http_response",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )

        return response

    app.add_middleware(
        SessionMiddleware,
        secret_key=config("SECRET_KEY"),
    )

    origins = ["http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        # allow_credentials=True,  # cross-origin for frontend
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", ".ngrok-free.app", "testserver"],
    )
