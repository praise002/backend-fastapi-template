# FastAPI Best Practices <!-- omit from toc -->
**COPIED**

> **Opinionated list of best practices and conventions we use at our startups.**

After several years of building production systems, we've made both good and bad decisions that significantly impacted our developer experience. Here are some lessons worth sharing.

---

> **Working with an AI agent?** See [AGENTS.md](./AGENTS.md) for the same rules in a terse, machine-readable format with a version matrix, Do/Don't blocks, and an anti-patterns checklist.


## Contents  <!-- omit from toc -->
- [Project Structure](#project-structure)
- [Async Routes](#async-routes)
  - [I/O Intensive Tasks](#io-intensive-tasks)
  - [CPU Intensive Tasks](#cpu-intensive-tasks)
- [Pydantic](#pydantic)
  - [Excessively use Pydantic](#excessively-use-pydantic)
  - [Custom Base Model](#custom-base-model)
  - [Decouple Pydantic BaseSettings](#decouple-pydantic-basesettings)
- [Dependencies](#dependencies)
  - [Beyond Dependency Injection](#beyond-dependency-injection)
  - [Chain Dependencies](#chain-dependencies)
  - [Decouple \& Reuse dependencies. Dependency calls are cached](#decouple--reuse-dependencies-dependency-calls-are-cached)
  - [Prefer `async` dependencies](#prefer-async-dependencies)
- [Miscellaneous](#miscellaneous)
  - [Follow the REST](#follow-the-rest)
  - [FastAPI response serialization](#fastapi-response-serialization)
  - [If you must use sync SDK, then run it in a thread pool.](#if-you-must-use-sync-sdk-then-run-it-in-a-thread-pool)
  - [BackgroundTasks vs a real task queue](#backgroundtasks-vs-a-real-task-queue)
  - [ValueErrors might become Pydantic ValidationError](#valueerrors-might-become-pydantic-validationerror)
  - [Docs](#docs)
  - [Set DB keys naming conventions](#set-db-keys-naming-conventions)
  - [Migrations. Alembic](#migrations-alembic)
  - [Set DB naming conventions](#set-db-naming-conventions)
  - [SQL-first. Pydantic-second](#sql-first-pydantic-second)
  - [Set tests client async from day 0](#set-tests-client-async-from-day-0)
    - [Override dependencies in tests](#override-dependencies-in-tests)
  - [Use ruff](#use-ruff)
- [Bonus Section](#bonus-section)

## Project Structure

There are many ways to structure a project, but the best structure is one that is **consistent, straightforward, and free of surprises**.

Many example projects and tutorials organize projects by file type (e.g., `crud`, `routers`, `models`), which works well for microservices or smaller projects. However, this approach doesn't scale well for monoliths with many domains and modules.

**Recommended structure** is inspired by Netflix's [Dispatch](https://github.com/Netflix/dispatch), with modifications:

```
fastapi-project
├── alembic/
├── src
│   ├── auth
│   │   ├── router.py
│   │   ├── schemas.py  # pydantic models
│   │   ├── models.py  # db models
│   │   ├── dependencies.py
│   │   ├── config.py  # local configs
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   ├── service.py
│   │   └── utils.py
│   ├── aws
│   │   ├── client.py  # client model for external service communication
│   │   ├── schemas.py
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   └── utils.py
│   ├── posts
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── models.py
│   │   ├── dependencies.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   ├── service.py
│   │   └── utils.py
│   ├── config.py  # global configs
│   ├── models.py  # global models
│   ├── exceptions.py  # global exceptions
│   ├── pagination.py  # global module e.g. pagination
│   ├── database.py  # db connection related stuff
│   └── main.py
├── tests/
│   ├── auth
│   ├── aws
│   └── posts
├── templates/
│   └── index.html
├── requirements
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── .env
├── .gitignore
├── logging.ini
└── alembic.ini
```

### Key Principles

1. **Store all domain directories inside `src` folder**
   - `src/` — highest level of the app, contains common models, configs, and constants
   - `src/main.py` — root of the project, initializes the FastAPI app

2. **Each package has its own router, schemas, models, etc.**
   - `router.py` — core of each module with all the endpoints
   - `schemas.py` — Pydantic models
   - `models.py` — database models
   - `service.py` — module-specific business logic  
   - `dependencies.py` — router dependencies
   - `constants.py` — module-specific constants and error codes
   - `config.py` — environment variables
   - `utils.py` — non-business logic functions (e.g., response normalization, data enrichment)
   - `exceptions.py` — module-specific exceptions (e.g., `PostNotFound`, `InvalidUserData`)

3. **Import from other packages explicitly**
   ```python
   from src.auth import constants as auth_constants
   from src.notifications import service as notification_service
   from src.posts.constants import ErrorCode as PostsErrorCode
   ```

## Async Routes

FastAPI is an **async-first framework**—it's designed to work with async I/O operations, which is why it's so fast.

However, FastAPI doesn't restrict you to only `async` routes; you can use `sync` routes too. This might confuse beginners, but they're **not the same**.

### I/O Intensive Tasks

FastAPI can [effectively handle](https://fastapi.tiangolo.com/async/#path-operation-functions) both async and sync I/O operations:

- **Sync routes** run in a [threadpool](https://en.wikipedia.org/wiki/Thread_pool), so blocking I/O operations won't block the [event loop](https://docs.python.org/3/library/asyncio-eventloop.html) from executing other tasks
- **Async routes** are called via `await` and FastAPI trusts you to only perform non-blocking I/O operations

**⚠️ Caveat:** If you execute blocking operations within async routes, the event loop won't be able to run other tasks until the blocking operation completes.

#### Example: Good vs. Bad Async Usage

```python
import asyncio
import time
from fastapi import APIRouter

router = APIRouter()

@router.get("/terrible-ping")
async def terrible_ping():
    """❌ DON'T: Blocking operation in async - blocks entire event loop"""
    time.sleep(10)  # Whole process blocked for 10 seconds
    return {"pong": True}

@router.get("/good-ping")
def good_ping():
    """✅ OK: Blocking operation in sync - runs in thread pool"""
    time.sleep(10)  # Blocks only this thread, not event loop
    return {"pong": True}

@router.get("/perfect-ping")
async def perfect_ping():
    """✅ BEST: Non-blocking operation in async"""
    await asyncio.sleep(10)  # Event loop continues processing other tasks
    return {"pong": True}
```

#### What Happens When Each Endpoint is Called

**`GET /terrible-ping`**
1. FastAPI server receives a request
2. Event loop and all queued tasks wait until `time.sleep()` finishes
   - Since the route is async, the server doesn't offload it to a threadpool
   - **Server won't accept new requests while waiting** ⚠️
3. Server returns the response
4. Only then does the server resume accepting new requests

**`GET /good-ping`**
1. FastAPI server receives a request
2. FastAPI sends the entire `good_ping` route to the threadpool
3. While `good_ping` executes, the event loop continues processing other tasks (requests, database calls)
   - The worker thread handles `time.sleep()` independently from the main thread
   - Non-blocking for the event loop ✅
4. When `good_ping` finishes, the server returns a response

**`GET /perfect-ping`**
1. FastAPI server receives a request
2. FastAPI awaits `asyncio.sleep(10)`
3. Event loop continues processing other tasks from the queue
4. When `asyncio.sleep(10)` completes, the server finishes and returns a response

#### ⚠️ Notes on Thread Pool

- **Threads are expensive** — they consume more resources than coroutines
- **Limited resources** — thread pool has a limited number of threads. You might run out and your app will become slow 
  - [Learn more](https://github.com/Kludex/fastapi-tips?tab=readme-ov-file#2-be-careful-with-non-async-functions)

### CPU Intensive Tasks

Non-blocking awaitables and threadpool offloading are only beneficial for **I/O intensive tasks** (database calls, file operations, API requests).

**CPU-intensive tasks** (heavy calculations, data processing, video transcoding) cannot benefit:
- **Async doesn't help** — the CPU must actively work to complete them
- **Threading doesn't help either** — due to the [GIL](https://realpython.com/python-gil/), only one thread can execute Python bytecode at a time

**Solution:** Offload CPU-intensive tasks to worker processes using:
- `multiprocessing`
- Task queue like **Celery**
- Background job workers

#### Related Resources

- [Architecture: Flask vs FastAPI](https://stackoverflow.com/questions/62976648/architecture-flask-vs-fastapi/70309597#70309597)
- [FastAPI uploadfile is slow compared to Flask](https://stackoverflow.com/questions/65342833/fastapi-uploadfile-is-slow-compared-to-flask)
- [FastAPI runs API calls in serial instead of parallel](https://stackoverflow.com/questions/71516140/fastapi-runs-api-calls-in-serial-instead-of-parallel-fashion)

## Pydantic

### Excessively Use Pydantic

Pydantic has a rich set of features for data validation and transformation. Beyond basic field validation, it includes:
- Regex validation
- Enums
- String manipulation
- Email validation
- And much more

#### Example: Comprehensive Pydantic Model

```python
from enum import StrEnum
from pydantic import AnyUrl, BaseModel, EmailStr, Field

class MusicBand(StrEnum):
    AEROSMITH = "AEROSMITH"
    QUEEN = "QUEEN"
    ACDC = "AC/DC"

class UserBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    username: str = Field(
        min_length=1, 
        max_length=128, 
        pattern="^[A-Za-z0-9-_]+$"
    )
    email: EmailStr
    age: int = Field(ge=18)  # Must be >= 18
    favorite_band: MusicBand | None = None  # Only specific values allowed
    website: AnyUrl | None = None
```

### Custom Base Model

Having a controllable global base model allows you to customize all models within the app. For example:
- Enforce a standard datetime format
- Introduce common methods for all subclasses
- Centralize serialization logic

#### Example: Custom Base Model

```python
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, field_serializer

class CustomModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_datetimes(self, value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=ZoneInfo("UTC"))
            return value.strftime("%Y-%m-%dT%H:%M:%S%z")
        return value

    def serializable_dict(self, **kwargs):
        """Return a dict which contains only serializable fields."""
        default_dict = self.model_dump()
        return jsonable_encoder(default_dict)
```

**Benefits:**
- Serializes all datetime fields to a **standard format with explicit timezone**
- Provides a method to return a dict with **only serializable fields**

### Decouple Pydantic BaseSettings

BaseSettings is excellent for reading environment variables, but a single monolithic BaseSettings for the whole app becomes messy. **Split it across modules and domains**.

#### Example: Modular Configuration

```python
# src/auth/config.py
from datetime import timedelta
from pydantic_settings import BaseSettings

class AuthConfig(BaseSettings):
    JWT_ALG: str
    JWT_SECRET: str
    JWT_EXP: int = 5  # minutes
    REFRESH_TOKEN_KEY: str
    REFRESH_TOKEN_EXP: timedelta = timedelta(days=30)
    SECURE_COOKIES: bool = True

auth_settings = AuthConfig()

# src/config.py
from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings
from src.constants import Environment

class Config(BaseSettings):
    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn
    SITE_DOMAIN: str = "myapp.com"
    ENVIRONMENT: Environment = Environment.PRODUCTION
    SENTRY_DSN: str | None = None
    CORS_ORIGINS: list[str]
    CORS_ORIGINS_REGEX: str | None = None
    CORS_HEADERS: list[str]
    APP_VERSION: str = "1.0"

settings = Config()
```

---```

## Dependencies

### Beyond Dependency Injection

Pydantic is great for schema validation, but for **complex validations** requiring database or external service calls, it's not enough.

FastAPI docs mostly present dependencies as **DI for endpoints**, but they're also excellent for **request validation**.

Dependencies can validate data against database constraints:
- Check if an email already exists
- Ensure a user exists
- Validate business logic constraints

#### Example: Validation Dependencies

```python
# dependencies.py
async def valid_post_id(post_id: UUID4) -> dict[str, Any]:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()
    return post

# router.py
@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post_by_id(post: dict[str, Any] = Depends(valid_post_id)):
    return post

@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    update_data: PostUpdate,  
    post: dict[str, Any] = Depends(valid_post_id), 
):
    updated_post = await service.update(id=post["id"], data=update_data)
    return updated_post

@router.get("/posts/{post_id}/reviews", response_model=list[ReviewsResponse])
async def get_post_reviews(post: dict[str, Any] = Depends(valid_post_id)):
    post_reviews = await reviews_service.get_by_post_id(post["id"])
    return post_reviews
```

**Benefits:**
- ✅ Reuse validation logic across endpoints
- ✅ DRY principle (don't repeat tests for each endpoint)
- ✅ Centralized validation logic

### Chain Dependencies

Dependencies can use other dependencies, avoiding code repetition for similar logic.

#### Example: Chained Validations

```python
# dependencies.py
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError

async def valid_post_id(post_id: UUID4) -> dict[str, Any]:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()
    return post

async def parse_jwt_data(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/auth/token"))
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, "JWT_SECRET", algorithms=["HS256"])
    except InvalidTokenError:
        raise InvalidCredentials()
    return {"user_id": payload["id"]}

async def valid_owned_post(
    post: dict[str, Any] = Depends(valid_post_id), 
    token_data: dict[str, Any] = Depends(parse_jwt_data),
) -> dict[str, Any]:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()
    return post

# router.py
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(post: dict[str, Any] = Depends(valid_owned_post)):
    return post
```

### Decouple & Reuse Dependencies — Dependency Calls are Cached

**Important:** FastAPI caches dependency results within a request's scope. If `valid_post_id` is called multiple times in one route, it's called **only once**.

This allows us to decouple dependencies into smaller functions that are easier to reuse:

#### Example: Dependency Reuse and Caching

```python
# dependencies.py
from fastapi import BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError

async def valid_post_id(post_id: UUID4) -> Mapping:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()
    return post

async def parse_jwt_data(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/auth/token"))
) -> dict:
    try:
        payload = jwt.decode(token, "JWT_SECRET", algorithms=["HS256"])
    except InvalidTokenError:
        raise InvalidCredentials()
    return {"user_id": payload["id"]}

async def valid_owned_post(
    post: Mapping = Depends(valid_post_id), 
    token_data: dict = Depends(parse_jwt_data),
) -> Mapping:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()
    return post

async def valid_active_creator(
    token_data: dict = Depends(parse_jwt_data),
):
    user = await users_service.get_by_id(token_data["user_id"])
    if not user["is_active"]:
        raise UserIsBanned()
    if not user["is_creator"]:
        raise UserNotCreator()
    return user

# router.py
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(
    worker: BackgroundTasks,
    post: Mapping = Depends(valid_owned_post),
    user: Mapping = Depends(valid_active_creator),
):
    """Get post that belongs to the active user."""
    worker.add_task(notifications_service.send_email, user["id"])
    return post
```

**In this example:**
- `parse_jwt_data` is used 3 times:
  1. `valid_owned_post` → `parse_jwt_data`
  2. `valid_active_creator` → `parse_jwt_data`
  3. `get_user_post`
- But it's **called only once** per request ✅

### Prefer `async` Dependencies

FastAPI supports both `sync` and `async` dependencies. Although it's tempting to use `sync` when you don't need to await anything, **prefer `async`**.

**Why?** Just like routes, `sync` dependencies run in a threadpool. Threads have overhead that's unnecessary for small non-I/O operations.

[Learn more](https://github.com/Kludex/fastapi-tips?tab=readme-ov-file#9-your-dependencies-may-be-running-on-threads)

---


## Miscellaneous
### Follow the REST
Developing RESTful API makes it easier to reuse dependencies in routes like these:
   1. `GET /courses/:course_id`
   2. `GET /courses/:course_id/chapters/:chapter_id/lessons`
   3. `GET /chapters/:chapter_id`

The only caveat is having to use the same variable names in the path:
- If you have two endpoints `GET /profiles/:profile_id` and `GET /creators/:creator_id`
that both validate whether the given `profile_id` exists,  but `GET /creators/:creator_id`
also checks if the profile is creator, then it's better to rename `creator_id` path variable to `profile_id` and chain those two dependencies.
```python
# src.profiles.dependencies
async def valid_profile_id(profile_id: UUID4) -> Mapping:
    profile = await service.get_by_id(profile_id)
    if not profile:
        raise ProfileNotFound()

    return profile

# src.creators.dependencies
async def valid_creator_id(profile: Mapping = Depends(valid_profile_id)) -> Mapping:
    if not profile["is_creator"]:
       raise ProfileNotCreator()

    return profile

# src.profiles.router.py
@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_user_profile_by_id(profile: Mapping = Depends(valid_profile_id)):
    """Get profile by id."""
    return profile

# src.creators.router.py
@router.get("/creators/{profile_id}", response_model=ProfileResponse)
async def get_user_profile_by_id(
     creator_profile: Mapping = Depends(valid_creator_id)
):
    """Get creator's profile by id."""
    return creator_profile

```
### FastAPI response serialization
You might think you can return a Pydantic object that matches your route's `response_model` and skip some processing steps, but you'd be wrong.

FastAPI first converts the Pydantic object to a dict using `jsonable_encoder`, then validates the data against your `response_model`, and only then serializes it to JSON.

This means your Pydantic model object is created twice:
- First, when you explicitly create it to return from your route.
- Second, implicitly by FastAPI to validate the response data according to the response_model.

```python
from fastapi import FastAPI
from pydantic import BaseModel, model_validator

app = FastAPI()


class ProfileResponse(BaseModel):
    @model_validator(mode="after")
    def debug_usage(self):
        print("created pydantic model")

        return self


@app.get("/", response_model=ProfileResponse)
async def root():
    return ProfileResponse()
```
**Logs Output:**
```
[INFO] [2022-08-28 12:00:00.000000] created pydantic model
[INFO] [2022-08-28 12:00:00.000020] created pydantic model
```

### If you must use sync SDK, then run it in a thread pool.
If you must use a library that's not `async`, run the HTTP calls in an external worker thread.

Use `run_in_threadpool` from Starlette.
```python
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from my_sync_library import SyncAPIClient 

app = FastAPI()


@app.get("/")
async def call_my_sync_library():
    my_data = await service.get_my_data()

    client = SyncAPIClient()
    await run_in_threadpool(client.make_request, data=my_data)
```

### BackgroundTasks vs a real task queue
FastAPI's `BackgroundTasks` is convenient — and a footgun if you misuse it. Tasks run **after the response is sent, in the same worker process**. If the worker dies, the task is gone. There is no retry, no visibility, no scheduling.

| Use `BackgroundTasks` when…                      | Use Celery / Arq / RQ when…                     |
|--------------------------------------------------|-------------------------------------------------|
| Task is short (< 1 second)                       | Task takes seconds to minutes                   |
| Failure can be silently dropped                  | You need retries or dead-letter handling        |
| It's in-process (send email, log a row)          | It's CPU-heavy or needs a separate worker pool  |
| You don't need scheduling or rate limiting       | You need cron, ETA, or rate limiting            |

```python
from fastapi import BackgroundTasks


@router.post("/signup")
async def signup(data: SignupIn, bg: BackgroundTasks):
    user = await service.create_user(data)
    bg.add_task(send_welcome_email, user.email)  # fire-and-forget, in-process
    return user
```
Rule of thumb: if you'd page someone when the task is lost, it doesn't belong in `BackgroundTasks`.

### ValueErrors might become Pydantic ValidationError
If you raise a `ValueError` in a Pydantic schema that's used directly in a request body, FastAPI will return a detailed validation error response to users.
```python
# src.profiles.schemas
from pydantic import BaseModel, field_validator

class ProfileCreate(BaseModel):
    username: str
    password: str
    
    @field_validator("password", mode="after")
    @classmethod
    def valid_password(cls, password: str) -> str:
        if not re.match(STRONG_PASSWORD_PATTERN, password):
            raise ValueError(
                "Password must contain at least "
                "one lower character, "
                "one upper character, "
                "digit or "
                "special symbol"
            )

        return password


# src.profiles.routes
from fastapi import APIRouter

router = APIRouter()


@router.post("/profiles")
async def create_profile(profile_data: ProfileCreate):
   pass
```
**Response Example:**

<img src="images/value_error_response.png" width="400" height="auto">

### Docs
1. Unless your API is public, hide docs by default. Show it explicitly on the selected envs only.
```python
from fastapi import FastAPI
from starlette.config import Config

config = Config(".env")  # parse .env file for env variables

ENVIRONMENT = config("ENVIRONMENT")  # get current env name
SHOW_DOCS_ENVIRONMENT = ("local", "staging")  # explicit list of allowed envs

app_configs = {"title": "My Cool API"}
if ENVIRONMENT not in SHOW_DOCS_ENVIRONMENT:
   app_configs["openapi_url"] = None  # set url for docs as null

app = FastAPI(**app_configs)
```
2. Help FastAPI to generate an easy-to-understand docs
   1. Set `response_model`, `status_code`, `description`, etc.
   2. If models and statuses vary, use `responses` route attribute to add docs for different responses
```python
from fastapi import APIRouter, status

router = APIRouter()

@router.post(
    "/endpoints",
    response_model=DefaultResponseModel,  # default response pydantic model 
    status_code=status.HTTP_201_CREATED,  # default status code
    description="Description of the well documented endpoint",
    tags=["Endpoint Category"],
    summary="Summary of the Endpoint",
    responses={
        status.HTTP_200_OK: {
            "model": OkResponse, # custom pydantic model for 200 response
            "description": "Ok Response",
        },
        status.HTTP_201_CREATED: {
            "model": CreatedResponse,  # custom pydantic model for 201 response
            "description": "Creates something from user request",
        },
        status.HTTP_202_ACCEPTED: {
            "model": AcceptedResponse,  # custom pydantic model for 202 response
            "description": "Accepts request and handles it later",
        },
    },
)
async def documented_route():
    pass
```
Will generate docs like this:
![FastAPI Generated Custom Response Docs](images/custom_responses.png "Custom Response Docs")

### Set DB keys naming conventions
Explicitly setting the indexes' namings according to your database's convention is preferable over sqlalchemy's. 
```python
from sqlalchemy import MetaData

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)
```
### Migrations. Alembic
1. Migrations must be static and reversible. If your migrations depend on dynamically generated data, make sure only the data itself is dynamic, not its structure.
2. Generate migrations with descriptive names and slugs. The slug is required and should explain the changes.
3. Set a human-readable file template for new migrations. We use the `*date*_*slug*.py` pattern, e.g., `2022-08-24_post_content_idx.py`
```
# alembic.ini
file_template = %%(year)d-%%(month).2d-%%(day).2d_%%(slug)s
```
### Set DB naming conventions
Being consistent with names is important. Some rules we followed:
1. lower_case_snake
2. singular form (e.g. `post`, `post_like`, `user_playlist`)
3. group similar tables with module prefix, e.g. `payment_account`, `payment_bill`, `post`, `post_like`
4. stay consistent across tables, but concrete namings are ok, e.g.
   1. use `profile_id` in all tables, but if some of them need only profiles that are creators, use `creator_id`
   2. use `post_id` for all abstract tables like `post_like`, `post_view`, but use concrete naming in relevant modules like `course_id` in `chapters.course_id`
5. `_at` suffix for datetime
6. `_date` suffix for date
### SQL-first. Pydantic-second
- Usually, database handles data processing much faster and cleaner than CPython will ever do. 
- It's preferable to do all the complex joins and simple data manipulations with SQL.
- It's preferable to aggregate JSONs in DB for responses with nested objects.

For new projects, reach for SQLAlchemy 2.0's async API (`AsyncSession`, `async_sessionmaker`). The example below uses `encode/databases` for brevity — the SQL-first principle is what matters; the client is interchangeable.
```python
# src.posts.service
from typing import Any

from pydantic import UUID4
from sqlalchemy import desc, func, select, text
from sqlalchemy.sql.functions import coalesce

from src.database import database, posts, profiles, post_review, products

async def get_posts(
    creator_id: UUID4, *, limit: int = 10, offset: int = 0
) -> list[dict[str, Any]]: 
    select_query = (
        select(
            (
                posts.c.id,
                posts.c.slug,
                posts.c.title,
                func.json_build_object(
                   text("'id', profiles.id"),
                   text("'first_name', profiles.first_name"),
                   text("'last_name', profiles.last_name"),
                   text("'username', profiles.username"),
                ).label("creator"),
            )
        )
        .select_from(posts.join(profiles, posts.c.owner_id == profiles.c.id))
        .where(posts.c.owner_id == creator_id)
        .limit(limit)
        .offset(offset)
        .group_by(
            posts.c.id,
            posts.c.type,
            posts.c.slug,
            posts.c.title,
            profiles.c.id,
            profiles.c.first_name,
            profiles.c.last_name,
            profiles.c.username,
            profiles.c.avatar,
        )
        .order_by(
            desc(coalesce(posts.c.updated_at, posts.c.published_at, posts.c.created_at))
        )
    )
    
    return await database.fetch_all(select_query)

# src.posts.schemas
from typing import Any

from pydantic import BaseModel, UUID4

   
class Creator(BaseModel):
    id: UUID4
    first_name: str
    last_name: str
    username: str


class Post(BaseModel):
    id: UUID4
    slug: str
    title: str
    creator: Creator

    
# src.posts.router
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/creators/{creator_id}/posts", response_model=list[Post])
async def get_creator_posts(creator: dict[str, Any] = Depends(valid_creator_id)):
   posts = await service.get_posts(creator["id"])

   return posts
```
### Set tests client async from day 0
Writing integration tests with DB will likely lead to messed up event loop errors in the future.
Set the async test client immediately, using [httpx](https://www.python-httpx.org/) with `ASGITransport`. Don't reach for `async_asgi_testclient` — it's unmaintained.

```python
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app  # inited FastAPI app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_post(client: AsyncClient):
    resp = await client.post("/posts")

    assert resp.status_code == 201
```

#### Override dependencies in tests
Don't monkeypatch internals. FastAPI's `dependency_overrides` lets you swap any dependency for a test fake — auth, external clients, anything you don't want hitting the network.

```python
from src.auth.dependencies import parse_jwt_data
from src.main import app


def fake_user():
    return {"user_id": "00000000-0000-0000-0000-000000000001"}


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[parse_jwt_data] = fake_user
    yield
    app.dependency_overrides.clear()
```

Unless you have synchronous database connections (excuse me?) or don't plan to write integration tests.

### Use ruff
With linters, you can forget about formatting the code and focus on writing the business logic.

[Ruff](https://github.com/astral-sh/ruff) is "blazingly-fast" new linter that replaces black, autoflake, isort, and supports more than 600 lint rules.

It's a popular good practice to use pre-commit hooks, but just using the script was ok for us.
```shell
#!/bin/sh -e
set -x

ruff check --fix src
ruff format src
```

## Bonus Section
Some very kind people shared their own experience and best practices that are definitely worth reading.
Check them out at [issues](https://github.com/zhanymkanov/fastapi-best-practices/issues) section of the project.

For instance, [lowercase00](https://github.com/zhanymkanov/fastapi-best-practices/issues/4) 
has described in details their best practices working with permissions & auth, class-based services & views, 
task queues, custom response serializers, configuration with dynaconf, etc.  

If you have something to share about your experience working with FastAPI, whether it's good or bad, 
you are very welcome to create a new issue. It is our pleasure to read it. 

# 101 FastAPI Tips by [The FastAPI Expert]

This repository contains tips and tricks for FastAPI. If you have any tip that you believe is useful, feel free
to open an issue or a pull request.

Consider sponsoring me on GitHub to support my work. With your support, I will be able to create more content like this.

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor%20me%20on-GitHub-%23EA4AAA)](https://github.com/sponsors/Kludex)

> [!TIP]
    Remember to **watch this repository** to receive notifications about new tips.

## 1. Install `uvloop` and `httptools`

By default, [Uvicorn][uvicorn] doesn't come with `uvloop` and `httptools` which are faster than the default
asyncio event loop and HTTP parser. You can install them using the following command:

```bash
pip install uvloop httptools
```

[Uvicorn][uvicorn] will automatically use them if they are installed in your environment.

> [!WARNING]
> `uvloop` can't be installed on Windows. If you use Windows locally, but Linux on production, you can use
> an [environment marker](https://peps.python.org/pep-0496/) to not install `uvloop` on Windows
> e.g. `uvloop; sys_platform != 'win32'`.

## 2. Be careful with non-async functions

There's a performance penalty when you use non-async functions in FastAPI. So, always prefer to use async functions.
The penalty comes from the fact that FastAPI will call [`run_in_threadpool`][run_in_threadpool], which will run the
function using a thread pool.

> [!NOTE]
    Internally, [`run_in_threadpool`][run_in_threadpool] will use [`anyio.to_thread.run_sync`][run_sync] to run the
    function in a thread pool.

> [!TIP]
    There are only 40 threads available in the thread pool. If you use all of them, your application will be blocked.

To change the number of threads available, you can use the following code:

```py
import anyio
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> Iterator[None]:
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = 100
    yield

app = FastAPI(lifespan=lifespan)
```

You can read more about it on [AnyIO's documentation][increase-threadpool].

## 3. Use `async for` instead of `while True` on WebSocket

Most of the examples you will find on the internet use `while True` to read messages from the WebSocket.

I believe the uglier notation is used mainly because the Starlette documentation didn't show the `async for` notation for a long time.

Instead of using the `while True`:

```py
from fastapi import FastAPI
from starlette.websockets import WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")
```

You can use the `async for` notation:

```py
from fastapi import FastAPI
from starlette.websockets import WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    async for data in websocket.iter_text():
        await websocket.send_text(f"Message text was: {data}")
```

You can read more about it on the [Starlette documentation][websockets-iter-data].

## 4. Ignore the `WebSocketDisconnect` exception

If you are using the `while True` notation, you will need to catch the `WebSocketDisconnect`.
The `async for` notation will catch it for you.

```py
from fastapi import FastAPI
from starlette.websockets import WebSocket, WebSocketDisconnect

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        pass
```

If you need to release resources when the WebSocket is disconnected, you can use that exception to do it.

If you are using an older FastAPI version, only the `receive` methods will raise the `WebSocketDisconnect` exception.
The `send` methods will not raise it. In the latest versions, all methods will raise it.
In that case, you'll need to add the `send` methods inside the `try` block.

## 5. Use HTTPX's `AsyncClient` instead of `TestClient`

Since you are using `async` functions in your application, it will be easier to use HTTPX's `AsyncClient`
instead of Starlette's `TestClient`.

```py
from fastapi import FastAPI


app = FastAPI()


@app.get("/")
async def read_root():
    return {"Hello": "World"}


# Using TestClient
from starlette.testclient import TestClient

client = TestClient(app)
response = client.get("/")
assert response.status_code == 200
assert response.json() == {"Hello": "World"}

# Using AsyncClient
import anyio
from httpx import AsyncClient, ASGITransport


async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert response.json() == {"Hello": "World"}


anyio.run(main)
```

If you are using lifespan events (`on_startup`, `on_shutdown` or the `lifespan` parameter), you can use the
[`asgi-lifespan`][asgi-lifespan] package to run those events.

```py
from contextlib import asynccontextmanager
from typing import AsyncIterator

import anyio
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    print("Starting app")
    yield
    print("Stopping app")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


async def main():
    async with LifespanManager(app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app)) as client:
            response = await client.get("/")
            assert response.status_code == 200
            assert response.json() == {"Hello": "World"}


anyio.run(main)
```

> [!NOTE]
    Consider supporting the creator of [`asgi-lifespan`][asgi-lifespan] [Florimond Manca][florimondmanca] via GitHub Sponsors.

## 6. Use Lifespan State instead of `app.state`

Since not long ago, FastAPI supports the [lifespan state], which defines a standard way to manage objects that need to be created at
startup, and need to be used in the request-response cycle.

The `app.state` is not recommended to be used anymore. You should use the [lifespan state] instead.

Using the `app.state`, you'd do something like this:

```py
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from httpx import AsyncClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncClient(app=app) as client:
        app.state.client = client
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root(request: Request):
    client = request.app.state.client
    response = await client.get("/")
    return response.json()
```

Using the lifespan state, you'd do something like this:

```py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypedDict, cast

from fastapi import FastAPI, Request
from httpx import AsyncClient


class State(TypedDict):
    client: AsyncClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    async with AsyncClient(app=app) as client:
        yield {"client": client}


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root(request: Request) -> dict[str, Any]:
    client = cast(AsyncClient, request.state.client)
    response = await client.get("/")
    return response.json()
```

## 7. Enable AsyncIO debug mode

If you want to find the endpoints that are blocking the event loop, you can enable the AsyncIO debug mode.

When you enable it, Python will print a warning message when a task takes more than 100ms to execute.

Run the following code with `PYTHONASYNCIODEBUG=1 python main.py`:

```py
import os
import time

import uvicorn
from fastapi import FastAPI


app = FastAPI()


@app.get("/")
async def read_root():
    time.sleep(1)  # Blocking call
    return {"Hello": "World"}


if __name__ == "__main__":
    uvicorn.run(app, loop="uvloop")
```

If you call the endpoint, you will see the following message:

```bash
INFO:     Started server process [19319]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     127.0.0.1:50036 - "GET / HTTP/1.1" 200 OK
Executing <Task finished name='Task-3' coro=<RequestResponseCycle.run_asgi() done, defined at /uvicorn/uvicorn/protocols/http/httptools_impl.py:408> result=None created at /uvicorn/uvicorn/protocols/http/httptools_impl.py:291> took 1.009 seconds
```

You can read more about it on the [official documentation](https://docs.python.org/3/library/asyncio-dev.html#debug-mode).

## 8. Implement a Pure ASGI Middleware instead of `BaseHTTPMiddleware`

The [`BaseHTTPMiddleware`][base-http-middleware] is the simplest way to create a middleware in FastAPI.

> [!NOTE]
> The `@app.middleware("http")` decorator is a wrapper around the `BaseHTTPMiddleware`.

There were some issues with the `BaseHTTPMiddleware`, but most of the issues were fixed in the latest versions.
That said, there's still a performance penalty when using it.

To avoid the performance penalty, you can implement a [Pure ASGI middleware]. The downside is that it's more complex to implement.

Check the Starlette's documentation to learn how to implement a [Pure ASGI middleware].

## 9. Your dependencies may be running on threads

If the function is non-async and you use it as a dependency, it will run in a thread.

In the following example, the `http_client` function will run in a thread:

```py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from httpx import AsyncClient
from fastapi import FastAPI, Request, Depends


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, AsyncClient]]:
    async with AsyncClient() as client:
        yield {"client": client}


app = FastAPI(lifespan=lifespan)


def http_client(request: Request) -> AsyncClient:
    return request.state.client


@app.get("/")
async def read_root(client: AsyncClient = Depends(http_client)):
    return await client.get("/")
```

To run in the event loop, you need to make the function async:
```py
# ...

async def http_client(request: Request) -> AsyncClient:
    return request.state.client

# ...
```

As an exercise for the reader, let's learn a bit more about how to check the running threads.

You can run the following with `python main.py`:

```py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from anyio.to_thread import current_default_thread_limiter
from httpx import AsyncClient
from fastapi import FastAPI, Request, Depends


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, AsyncClient]]:
    async with AsyncClient() as client:
        yield {"client": client}


app = FastAPI(lifespan=lifespan)


# Change this function to be async, and rerun this application.
def http_client(request: Request) -> AsyncClient:
    return request.state.client


@app.get("/")
async def read_root(client: AsyncClient = Depends(http_client)): ...


async def monitor_thread_limiter():
    limiter = current_default_thread_limiter()
    threads_in_use = limiter.borrowed_tokens
    while True:
        if threads_in_use != limiter.borrowed_tokens:
            print(f"Threads in use: {limiter.borrowed_tokens}")
            threads_in_use = limiter.borrowed_tokens
        await anyio.sleep(0)


if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(app="main:app")
    server = uvicorn.Server(config)

    async def main():
        async with anyio.create_task_group() as tg:
            tg.start_soon(monitor_thread_limiter)
            await server.serve()

    anyio.run(main)
```

If you call the endpoint, you will see the following message:

```bash
❯ python main.py
INFO:     Started server process [23966]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
Threads in use: 1
INFO:     127.0.0.1:57848 - "GET / HTTP/1.1" 200 OK
Threads in use: 0
```

Replace the `def http_client` with `async def http_client` and rerun the application.
You will not see the message `Threads in use: 1`, because the function is running in the event loop.

> [!TIP]
> You can use the [FastAPI Dependency] package that I've built to make it explicit when a dependency should run in a thread.

## 10. Use `pytest.mark.anyio` instead of `pytest.mark.asyncio`

You already have [`anyio`](https://github.com/agronholm/anyio) installed, since it's a dependency of Starlette.
Which means, you can use `pytest.mark.anyio` instead of `pytest.mark.asyncio`.

```py
import pytest

@pytest.mark.anyio
async def test_async_function(): ...
```

By default, `anyio` runs every test that has the marker twice, once with `trio` and another time with `asyncio`.
You probably want to restrict that by using either one or the other, in case you are testing an application,
and not a package:

```py
import pytest

@pytest.fixture
def anyio_backend():
    return "asyncio"  # or "trio"
```

You can read more about it on the
[`anyio` documentation](https://anyio.readthedocs.io/en/stable/testing.html#specifying-the-backends-to-run-on).

[uvicorn]: https://www.uvicorn.org/
[run_sync]: https://anyio.readthedocs.io/en/stable/threads.html#running-a-function-in-a-worker-thread
[run_in_threadpool]: https://github.com/encode/starlette/blob/9f16bf5c25e126200701f6e04330864f4a91a898/starlette/concurrency.py#L36-L42
[increase-threadpool]: https://anyio.readthedocs.io/en/stable/threads.html#adjusting-the-default-maximum-worker-thread-count
[websockets-iter-data]: https://www.starlette.io/websockets/#iterating-data
[florimondmanca]: https://github.com/sponsors/florimondmanca
[asgi-lifespan]: https://github.com/florimondmanca/asgi-lifespan
[lifespan state]: https://asgi.readthedocs.io/en/latest/specs/lifespan.html#lifespan-state
[The FastAPI Expert]: https://github.com/Kludex
[base-http-middleware]: https://www.starlette.io/middleware/#basehttpmiddleware
[pure ASGI middleware]: https://www.starlette.io/middleware/#pure-asgi-middleware
[FastAPI Dependency]: https://github.com/kludex/fastapi-dependency

## Claude Prompts

Leverage AI coding tools effectively with structured prompting patterns. Use these templates when working with Claude to maximize code quality and architecture.

### 1️⃣ Complete Application from Scratch

Think like a senior full-stack engineer developing a **complete, production-ready application.**

**Process:**
- First, design the system architecture
- Then develop the minimal but scalable version

**Deliverables:**
- ✅ Architecture diagram
- ✅ File structure
- ✅ Database schema
- ✅ API endpoints
- ✅ UI architecture
- ✅ Complete, scalable code

**Best for:** Building new projects with startup MVP mindset and scalability considerations.

### 2️⃣ Codebase Understanding and Refactoring

**Role:** Think like a senior engineer who just joined a large, unfamiliar codebase.

**Process:**
- Analyze the entire architecture and data flow
- Identify structural problems, duplicated code, performance bottlenecks, maintainability risks

**Deliverables:**
- ✅ Architecture summary
- ✅ Problem areas with severity levels
- ✅ Refactoring strategies
- ✅ Improved code

**Key Point:** Functionality remains unchanged — quality is enhanced.

### 3️⃣ Senior Debugging Engineer

**Role:** Think like a senior debugging engineer investigating bugs in production.

**Process:**
- Carefully analyze the code
- Think step by step through execution flow
- Find the root cause with edge cases
- Propose robust solutions

**Deliverables:**
- ✅ Code functionality explanation
- ✅ Problem diagnosis
- ✅ Why it fails
- ✅ Edge case analysis
- ✅ Fixed production-ready code

### 4️⃣ System Design + Implementation

**Role:** Think like a senior systems architect.

**Process:**
- Design a scalable system for the product
- Develop the minimal production version

**Deliverables:**
- ✅ System architecture
- ✅ Component structure
- ✅ Data flow diagrams
- ✅ API design specifications
- ✅ Database schema
- ✅ Caching strategy
- ✅ Implementation code

### 5️⃣ Performance Optimization Tips

**Role:** Think like a performance engineer optimizing for production.

**Goals:**
- ⚡ Minimize latency
- 💾 Reduce memory usage
- 📈 Improve scalability

**Process:**
- Find performance bottlenecks
- Identify inefficient logic
- Remove unnecessary operations

**Deliverables:**
- ✅ Performance issues identified
- ✅ Optimization strategies
- ✅ Improved, benchmarked code

### 6️⃣ Clean Architecture Rebuild

**Role:** Think like a senior engineer converting code to clean architecture patterns.

**Goals:**
- 🏗️ Separate concerns
- 🧩 Increase modularity
- 🔗 Reduce coupling

**Deliverables:**
- ✅ New folder structure
- ✅ Architecture documentation
- ✅ Refactored code

**Key Point:** Behavior remains unchanged — structure is improved.

### 7️⃣ Claude Multi-Agent Workflow

**Setup:** You are 4 collaborating agents working on the same task.

**Agents & Roles:**
| Agent | Responsibility |
|-------|-----------------|
| 🏛️ **Architect** | Design system architecture |
| 🔧 **Engineer** | Develop implementation |
| 👀 **Reviewer** | Quality control & standards |
| ⚡ **Optimizer** | Performance improvement |

**Deliverables:**
- ✅ Architecture & design
- ✅ Complete implementation
- ✅ Review feedback & improvements
- ✅ Final optimized version

### 8️⃣ Production-Level UI Component Builder

**Role:** Think like a senior frontend engineer building reusable components.

**Requirements:**
- ✅ Reusable across the application
- ✅ Accessible (WCAG compliant)
- ✅ Production-ready

**Considerations:**
- 📍 Loading states and error handling
- 🎯 Edge cases and boundary conditions
- 📱 Responsive design patterns
- ♿ Accessibility standards

**Deliverables:**
- ✅ Component architecture
- ✅ Props design & typing
- ✅ Implementation with examples
- ✅ Usage documentation

### 🔑 Key Effective AI Engineering Pattern

Modern AI-assisted development is a **3-step system**:

#### Step 1: Create Mental Model
Have Claude analyze your entire repository and generate a **detailed architecture document** with diagrams (Mermaid). This establishes deep context before any coding.

```
Prompt: "Analyze this codebase and provide:
- System architecture overview
- Data flow diagrams
- Key components and dependencies
- Technology stack summary"
```

#### Step 2: Define Requirements with PRD
Instead of immediately coding, ask Claude to act as **Product Manager** and produce a structured PRD with **user stories** and **acceptance criteria** based on the existing system.

```
Prompt: "Based on the architecture, create a PRD for [feature]:
- User stories
- Acceptance criteria
- Technical requirements
- Integration points"
```

#### Step 3: Iteratively Implement Using Context
Instruct Claude to build the feature **step-by-step** (MVP first), referencing the architecture doc and PRD as guardrails, updating progress continuously.

```
Prompt: "Using the architecture and PRD provided:
1. Outline the implementation plan
2. Build the minimal viable version
3. Handle edge cases
4. Add comprehensive tests"
```

**Why This Works:**
- 🎯 Structured context → Better code decisions
- 📊 PRD alignment → No scope creep
- 🔄 Iterative approach → Lower risk of major rewrites

---

## REST Principles

Build maintainable, scalable APIs by following these proven REST guidelines.

### Core REST Patterns

#### 1. **Follow RESTful Principles**
✅ Use resources as nouns, not verbs: `/users`, `/posts`, not `/getUsers`  
✅ Use HTTP verbs for actions: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`  
✅ Stateless endpoints — each request contains all necessary context

#### 2. **Clear, Consistent Naming Conventions**
✅ Use lowercase with hyphens for multi-word endpoints: `/user-profiles`, `/api-keys`  
✅ Use plural nouns for collections: `/users`, not `/user`  
✅ Use singular nouns for single resources: `/users/{id}`, `/posts/{id}/comments/{comment_id}`

#### 3. **Version Your API**
✅ Always include version in URL: `/v1/users`, `/v2/products`  
✅ Maintains backward compatibility during transitions  
✅ Allows deprecation of old versions gracefully

```python
router = APIRouter(prefix="/v1")  # Include in all routers
```

#### 4. **Use Proper HTTP Status Codes**
✅ `200 OK` — Successful GET, PUT, PATCH  
✅ `201 Created` — Successful POST creating a resource  
✅ `204 No Content` — Successful DELETE  
✅ `400 Bad Request` — Client validation errors  
✅ `401 Unauthorized` — Authentication required/failed  
✅ `403 Forbidden` — Authenticated but not authorized  
✅ `404 Not Found` — Resource doesn't exist  
✅ `409 Conflict` — Resource already exists (duplicate)  
✅ `429 Too Many Requests` — Rate limit exceeded  
✅ `500 Internal Server Error` — Server-side error

#### 5. **Implement Pagination for Large Responses**
✅ Always paginate collections to prevent overwhelming clients  
✅ Use `skip` and `limit` or `page` and `page_size` parameters

```python
@router.get("/posts", response_model=list[PostSchema])
async def list_posts(skip: int = 0, limit: int = 10):
    return await service.get_posts(skip=skip, limit=limit)
```

#### 6. **Apply Rate Limiting and Throttling**
✅ Protect endpoints from abuse with slowapi or alternatives  
✅ Different limits for different endpoints (auth stricter than public)  
✅ Return `429 Too Many Requests` with retry info

#### 7. **Secure Your API with Authentication & HTTPS**
✅ Use **JWT tokens** for stateless authentication  
✅ Use **OAuth2** for third-party integrations  
✅ **Always** use HTTPS in production (never HTTP)  
✅ Implement token rotation and refresh strategies

#### 8. **Provide Meaningful Error Messages**
✅ Include error code, description, and context  
❌ Don't expose internal stack traces or database details

```python
{
  "error": {
    "code": "INVALID_EMAIL",
    "message": "Email format is invalid",
    "field": "email"
  }
}
```

#### 9. **Document Your API with OpenAPI/Swagger**
✅ FastAPI automatically generates OpenAPI docs  
✅ Add descriptions and examples to endpoints and schemas  
✅ Keep docs synchronized with actual API

```python
@router.get("/users/{user_id}")
async def get_user(user_id: UUID):
    """Retrieve a specific user by ID."""
    return await db.get_user(user_id)
```

#### 10. **Use Standard Request/Response Formats**
✅ **Always** use JSON for modern APIs  
✅ Consistent response envelope structure  
✅ Predictable field naming conventions

```python
# Consistent response structure
{
  "success": true,
  "data": {...},
  "message": "Resource created successfully"
}
```

#### 11. **Enable CORS for Cross-Domain Requests**
✅ Configure explicitly, don't allow all origins in production  
✅ Specify required methods and headers

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frontend.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```
```

**Why This Works:**
- 🎯 Structured context → Better code decisions
- 📊 PRD alignment → No scope creep
- 🔄 Iterative approach → Lower risk of major rewrites

1. Create a “mental model” of the codebase
First, have the AI analyze the entire repository and generate a detailed architecture document (with diagrams like Mermaid). This helps the AI understand the app before doing any work.

2.  Define requirements with a Product Requirements Document (PRD)
Instead of immediately coding features, ask the AI to act as a product manager and produce a structured PRD with user stories and requirements based on the existing system.

3. Iteratively implement features using the PRD + context
Then instruct the AI to build the feature step-by-step (starting with an MVP), using the architecture doc and PRD as reference, and update progress continuously.

Overall insight:
Better AI coding results come from giving structured context first (architecture + PRD), then implementing features iteratively, rather than prompting the AI to “just build something” immediately.

REST PRINCIPLES

1. Follow RESTful principles


2. Use clear, consistent naming conventions.

3. Version your API.
/v1/users


4. Use proper HTTP status codes.


5. Implement pagination for large responses.


6. Apply rate limiting and throttling.


7. Secure your API with authentication (JWT, OAuth) and HTTPS.


8. Provide meaningful error messages.


9. Document your API with OpenAPI/Swagger.


10. Use standard request/response formats like JSON.


11. Enable CORS for cross-domain requests.


12. Optimize performance (caching, compression).


13. Implement logging and monitoring.


14. Validate all incoming data.


15. Ensure backward compatibility or versioning.


16. Follow security best practices (input sanitization, HTTPS).

17. Use Query Parameters for Filtering, Sorting, and Pagination.
/products?category=electronics&sort=price&limit=10

Query parameters are utilized to filter results, sort data, or display specific data fields

18. Organize URLs into a Hierarchical Structure.
/projects/123/tasks (tasks belonging to project 123)

19. Use Plural Nouns for Collection Resources.
/books (collection of books)
/books/123 (specific book with ID 123)

20. Use Nouns to Represent Resources, Not Verbs.
