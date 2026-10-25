"""Dish photos (FR-29): check the upload, turn it upright, shrink it, store it as JPEG.

Phone photos are often 4000 px and several MB; employees see them small on a phone, so 1200 px is plenty.
"""
import io
import uuid

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from apps.core.exceptions import DomainError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SIDE = 1200
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def prepare_dish_photo(upload) -> ContentFile:
    if upload.size > MAX_UPLOAD_BYTES:
        raise DomainError("photo_too_large", "The photo must be 5 MB or less.")
    try:
        image = Image.open(upload)
        if image.format not in ALLOWED_FORMATS:
            raise DomainError("photo_invalid", "Use a JPEG, PNG or WebP photo.")
        image = ImageOps.exif_transpose(image)  # phone photos store their rotation in EXIF
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGBA")
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    except DomainError:
        raise
    except Exception as exc:  # not an image, truncated, or too many pixels (decompression bomb)
        raise DomainError("photo_invalid", "Use a JPEG, PNG or WebP photo.") from exc
    return ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex}.jpg")
