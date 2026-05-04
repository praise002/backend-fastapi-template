import logging
from contextlib import asynccontextmanager

import asyncpg
import jinja2
import sentry_sdk
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette_admin.contrib.sqla import Admin, ModelView
from tenacity import retry, stop_after_delay, wait_fixed

from custom_logging import setup_logging
from src.auth.router import router as auth_router
from src.config import Config
from src.db.main import async_engine
from src.db.models import User
from src.errors import register_all_errors
from src.limiter import limiter
from src.middleware import register_middleware
from src.profiles.router import router as profile_router

setup_logging()

def custom_generate_unique_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags else "default"
    return f"{tag}-{route.name}"


if Config.SENTRY_DSN and Config.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(Config.SENTRY_DSN), enable_tracing=True)

description = """
## DEMO TEST PROJECT
"""

version = "v1"

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if Config.ENVIRONMENT != "test":   # ← skip in tests
        # Startup: wait for DB
        await wait_for_db()
    yield
    # Shutdown

app = FastAPI(
    title=Config.PROJECT_NAME,
    description=description,
    version=version,
    lifespan=lifespan,
    docs_url=f"{Config.API_V1_STR}/docs",
    redoc_url=f"{Config.API_V1_STR}/redoc",
    generate_unique_id_function=custom_generate_unique_id,
    openapi_url=f"{Config.API_V1_STR}/openapi.json",
    contact={
        "name": "Demo admin",
        "email": "demo@gmail.com",
    },
    
)

register_all_errors(app)

register_middleware(app)

app.state.limiter = limiter

env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"))
templates = Jinja2Templates(env=env)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Create admin
admin = Admin(async_engine, title="Demo")

# Add view
admin.add_view(ModelView(User, icon="fas fa-user"))

# Mount admin to your app
admin.mount_to(app)

app.include_router(auth_router, prefix=f"/api/{version}/auth", tags=["Auth"])
app.include_router(profile_router, prefix=f"/api/{version}/profiles", tags=["Profiles"])



@retry(stop=stop_after_delay(30), wait=wait_fixed(1))
async def wait_for_db():
    """Wait for database to be ready"""
    try:
        conn = await asyncpg.connect(str(Config.DATABASE_URL))
        await conn.close()
    except Exception as e:
        logging.info(f"DB not ready: {e}")
        raise



# Custom OpenAPI schema to override 422 validation error response
def custom_openapi():
    """
    Customize the OpenAPI schema to show our custom validation error format
    in Swagger docs instead of FastAPI's default format.
    """
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    # Generate the default OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Define custom validation error schema
    custom_validation_error = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "example": "error",
                "description": "Status of the response",
            },
            "message": {
                "type": "string",
                "example": "Validation error",
                "description": "Error message",
            },
            "errors": {
                "type": "array",
                "description": "List of validation errors",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {
                            "type": "string",
                            "example": "email",
                            "description": "Field that failed validation",
                        },
                        "message": {
                            "type": "string",
                            "example": "value is not a valid email address",
                            "description": "Validation error message",
                        },
                    },
                    "required": ["field", "message"],
                },
            },
        },
        "required": ["status", "message", "errors"],
    }

    # Override the HTTPValidationError schema
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "schemas" not in openapi_schema["components"]:
        openapi_schema["components"]["schemas"] = {}

    openapi_schema["components"]["schemas"][
        "HTTPValidationError"
    ] = custom_validation_error

    # Also remove the default ValidationError schema as it's no longer needed
    openapi_schema["components"]["schemas"].pop("ValidationError", None)

    # Cache the schema
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Override FastAPI's openapi method
app.openapi = custom_openapi  # type: ignore


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url=f"/api/{version}/docs")


@app.get("/health", tags=["Health"], include_in_schema=False)
async def health_check():
    return {"status": "ok"}
