import cloudinary.uploader
from fastapi import HTTPException, UploadFile

from src.errors import (
    FileTooLarge,
    ImageUploadFailed,
    InvalidFileContent,
    InvalidFileType,
    NoFilenameProvided,
)


class CloudinaryService:
    """Service for handling Cloudinary operations"""

    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    MEDIA_TAG = "devsearch/media"

    @staticmethod
    def validate_image(file: UploadFile) -> None:
        """Validate uploaded image file"""

        if not file.filename:
            raise NoFilenameProvided()

        file_ext = file.filename.split(".")[-1].lower()
        if file_ext not in CloudinaryService.ALLOWED_EXTENSIONS:
            allowed = ", ".join(CloudinaryService.ALLOWED_EXTENSIONS)
            raise InvalidFileType(
                message=f"Invalid file type. Allowed types: {allowed}"
            )

        if not file.content_type or not file.content_type.startswith("image/"):
            raise InvalidFileContent()

    @staticmethod
    async def upload_image(
        file: UploadFile,
        folder: str = "avatars",
        public_id: str | None = None,
        overwrite: bool = True,
    ) -> dict:
        """
        Upload image to Cloudinary

        Args:
            file: The uploaded file
            folder: Cloudinary folder to store the image
            public_id: Optional custom public ID for the image
            overwrite: Whether to overwrite existing image with same public_id

        Returns:
            dict: Upload response containing secure_url and other metadata

        Raises:
            Exception: If upload fails
        """
        try:
            CloudinaryService.validate_image(file)

            contents = await file.read()

            if len(contents) > CloudinaryService.MAX_FILE_SIZE:
                max_size_mb = CloudinaryService.MAX_FILE_SIZE / (1024 * 1024)
                raise FileTooLarge(
                    message=f"File size exceeds maximum allowed size of {max_size_mb}MB"
                )

            upload_options = {
                "folder": folder,
                "tags": [CloudinaryService.MEDIA_TAG],
                "overwrite": overwrite,
                "resource_type": "image",
                "format": "jpg",  # Convert all images to jpg
                "transformation": [
                    {
                        "width": 500,
                        "height": 500,
                        "crop": "fill",
                        "gravity": "face",
                    },  # Auto-crop to face
                    {"quality": "auto:good"},  # Auto quality optimization
                ],
            }

            if public_id:
                upload_options["public_id"] = public_id

            result = cloudinary.uploader.upload(contents, **upload_options)

            return result["secure_url"]

        except HTTPException:
            raise
        except Exception as e:
            raise ImageUploadFailed(message=f"Failed to upload image: {str(e)}")

    @staticmethod
    async def upload_image_from_url(
        image_url: str,
        folder: str = "avatars",
        public_id: str | None = None,
        overwrite: bool = True,
    ) -> str | None:
        """
        Upload image from URL directly to Cloudinary

        Args:
            image_url: URL of the image to upload
            folder: Cloudinary folder
            public_id: Optional custom public ID
            overwrite: Whether to overwrite existing

        Returns:
            str: Secure URL of uploaded image, or None if failed
        """
        try:
            upload_options = {
                "folder": folder,
                "tags": [CloudinaryService.MEDIA_TAG],
                "overwrite": overwrite,
                "resource_type": "image",
                "format": "jpg",
                "transformation": [
                    {
                        "width": 500,
                        "height": 500,
                        "crop": "fill",
                        "gravity": "face",
                    },
                    {"quality": "auto:good"},
                ],
            }

            if public_id:
                upload_options["public_id"] = public_id

            # Cloudinary can download from URL directly!
            result = cloudinary.uploader.upload(image_url, **upload_options)

            return result["secure_url"]

        except Exception as e:
            # Don't raise - just log and return None (background task)
            import logging

            logging.error(
                "Failed to upload profile picture from URL",
                extra={"image_url": image_url, "error": str(e)},
            )
            return None

    @staticmethod
    async def delete_image(public_id: str) -> bool:
        """
        Delete image from Cloudinary

        Args:
            public_id: The public ID of the image to delete

        Returns:
            bool: True if deletion was successful
        """
        try:
            result = cloudinary.uploader.destroy(public_id)
            return result.get("result") == "ok"
        except Exception:
            return False

    @staticmethod
    def extract_public_id_from_url(url: str) -> str | None:
        """
        Extract public_id from Cloudinary URL

        Args:
            url: Cloudinary image URL

        Returns:
            str: The public_id or None if extraction fails
        """
        try:
            # Example URL: https://res.cloudinary.com/demo/image/upload/v1234567890/avatars/user123.jpg
            # We want: avatars/user123
            parts = url.split("/upload/")
            if len(parts) > 1:
                path_parts = parts[1].split("/")[1:]
                public_id_with_ext = "/".join(path_parts)
                public_id = public_id_with_ext.rsplit(".", 1)[0]
                return public_id
        except Exception:
            pass
        return None
