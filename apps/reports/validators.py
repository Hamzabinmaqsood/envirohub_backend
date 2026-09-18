from rest_framework import serializers

MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_report_image(image):
    if image.size > MAX_IMAGE_SIZE:
        raise serializers.ValidationError("Each image must be 10 MB or smaller.")
    content_type = getattr(image, "content_type", None)
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise serializers.ValidationError("Only JPEG, PNG, and WebP images are allowed.")
    return image
