import re
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from .models import ShortURL
from .utils import RESERVED_CODES, generate_code

User = get_user_model()
ALIAS_RE = re.compile(r"^[0-9A-Za-z_-]{3,32}$")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class ShortURLSerializer(serializers.ModelSerializer):
    custom_alias = serializers.CharField(write_only=True, required=False)
    short_url = serializers.SerializerMethodField()

    class Meta:
        model = ShortURL
        fields = [
            "short_code", "short_url", "original_url", "custom_alias",
            "is_active", "expires_at", "click_count", "created_at",
        ]
        read_only_fields = ["short_code", "click_count", "created_at"]

    def get_short_url(self, obj):
        return f"{settings.BASE_URL}/{obj.short_code}/"

    def validate_original_url(self, value):
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            raise serializers.ValidationError("Only http/https URLs are allowed.")
        own_host = urlparse(settings.BASE_URL).hostname
        if parsed.hostname and parsed.hostname == own_host:
            raise serializers.ValidationError("Cannot shorten a link that points to this service.")
        return value

    def validate_custom_alias(self, value):
        if not ALIAS_RE.match(value):
            raise serializers.ValidationError("3-32 chars: letters, digits, '-' and '_' only.")
        if value.lower() in RESERVED_CODES:
            raise serializers.ValidationError("This alias is reserved.")
        if ShortURL.objects.filter(short_code=value).exists():
            raise serializers.ValidationError("This alias is already taken.")
        return value

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("expires_at must be in the future.")
        return value

    def create(self, validated_data):
        owner = self.context["request"].user
        alias = validated_data.pop("custom_alias", None)
        if alias:
            try:
                with transaction.atomic():
                    return ShortURL.objects.create(owner=owner, short_code=alias, **validated_data)
            except IntegrityError:  # lost a race with another request
                raise serializers.ValidationError({"custom_alias": "This alias is already taken."})
        for _ in range(5):  # random code collisions are astronomically rare, retry anyway
            try:
                with transaction.atomic():
                    return ShortURL.objects.create(owner=owner, short_code=generate_code(), **validated_data)
            except IntegrityError:
                continue
        raise serializers.ValidationError("Could not generate a unique short code, please retry.")

    def update(self, instance, validated_data):
        validated_data.pop("custom_alias", None)  # alias is immutable after creation
        return super().update(instance, validated_data)
