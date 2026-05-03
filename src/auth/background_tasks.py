import logging

from src.auth.service import UserService
from src.cloudinary_service import CloudinaryService
from src.db.main import get_session


async def upload_profile_picture_task(
    user_id: str, image_url: str, folder: str = "avatars"
):
    """
    Background task to download and upload profile picture

    Args:
        user_id: User's ID (for public_id and database update)
        image_url: URL of the profile picture to download
        folder: Cloudinary folder to store the image
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
        # Step 1: Upload to Cloudinary (it downloads from URL automatically)
        cloudinary_url = await CloudinaryService.upload_image_from_url(
            image_url=image_url,
            folder=folder,
            public_id=f"user_{user_id}",
            overwrite=True,
        )

        if not cloudinary_url:
            logging.warning(
                "Profile picture upload failed",
                extra={
                    "event_type": "profile_picture_upload_failed",
                    "user_id": user_id,
                    "image_url": image_url,
                },
            )
            return

        # Step 2: Update user's profile picture in database
        async for session in get_session():
            user_service = UserService()
            user = await user_service.get_user(user_id, session)

            if user:
                await user_service.update_user(
                    user, {"avatar_url": cloudinary_url}, session
                )

                logging.info(
                    "Profile picture uploaded successfully",
                    extra={
                        "event_type": "profile_picture_upload_success",
                        "user_id": user_id,
                        "cloudinary_url": cloudinary_url,
                    },
                )
            else:
                logging.warning(
                    "User not found for profile picture update",
                    extra={
                        "event_type": "profile_picture_user_not_found",
                        "user_id": user_id,
                    },
                )

    except Exception as e:
        logging.exception(
            "Error in profile picture upload task",
            extra={
                "event_type": "profile_picture_upload_error",
                "user_id": user_id,
                "error": str(e),
            },
        )
