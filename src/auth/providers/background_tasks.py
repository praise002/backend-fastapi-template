"""
Provider Layer — Background Tasks
===================================
Providers interact with external systems — here, Cloudinary and the database.
They are similar to services but specialised for external integrations.

This module contains tasks enqueued via FastAPI's BackgroundTasks mechanism.
They run outside the HTTP request/response cycle, so they open their own
DB sessions rather than receiving one from a dependency.

Dependency direction: inward only.
  - Imports from: services, infrastructure
  - Must NOT import from: controllers i.e routers
"""

import logging

from src.auth.providers.cloudinary_service import CloudinaryService
from src.auth.service import UserService
from src.db.database import get_session

_user_service = UserService()


async def upload_profile_picture_task(
    user_id: str,
    image_url: str,
    folder: str = "avatars",
) -> None:
    """
    Background provider task: download a profile picture from a URL and
    store it in Cloudinary, then update the user's avatar_url in the DB.

    Args:
        user_id:   The user's ID (used as the Cloudinary public_id and for DB lookup).
        image_url: Remote URL of the picture to upload (e.g. Google profile photo).
        folder:    Cloudinary folder to store the image in.
    """
    logging.info(
        "Starting profile picture upload task",
        extra={
            "event_type": "profile_picture_upload_start",
            "user_id": user_id,
            "image_url": image_url,
        },
    )

    try:
        # Step 1 — Upload to Cloudinary 
        cloudinary_url = await CloudinaryService.upload_image_from_url(
            image_url=image_url,
            folder=folder,
            public_id=f"user_{user_id}",
            overwrite=True,
        )

        if not cloudinary_url:
            logging.warning(
                "Profile picture upload returned no URL",
                extra={
                    "event_type": "profile_picture_upload_failed",
                    "user_id": user_id,
                    "image_url": image_url,
                },
            )
            return

        # Step 2 — Persist the Cloudinary URL on the user's record
        async for session in get_session():
            user = await _user_service.get_user(user_id, session)

            if user:
                await _user_service.update_user(
                    user, {"avatar_url": cloudinary_url}, session
                )
                logging.info(
                    "Profile picture uploaded and saved",
                    extra={
                        "event_type": "profile_picture_upload_success",
                        "user_id": user_id,
                        "cloudinary_url": cloudinary_url,
                    },
                )
            else:
                logging.warning(
                    "User not found during profile picture update",
                    extra={
                        "event_type": "profile_picture_user_not_found",
                        "user_id": user_id,
                    },
                )

    except Exception:
        logging.exception(
            "Unhandled error in profile picture upload task",
            extra={
                "event_type": "profile_picture_upload_error",
                "user_id": user_id,
            },
        )
