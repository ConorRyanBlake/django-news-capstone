"""Serializers for the news app's REST API.

Each serializer translates a Django model to/from JSON. The pattern
is identical to the e-commerce API from Task 14 — ModelSerializer
handles the boring field-by-field mapping, and we override fields
where we want a friendlier representation (nested user info instead
of just a user ID, for example).
"""

from rest_framework import serializers

from .models import Article, CustomUser, Newsletter, Publisher


class CustomUserSerializer(serializers.ModelSerializer):
    """Compact public representation of a user.

    Deliberately excludes password, is_staff, is_superuser, and
    other sensitive fields. Used as the nested representation in
    Article and Newsletter serializers.
    """

    class Meta:
        model = CustomUser
        fields = ("id", "username", "email", "role")
        read_only_fields = fields


class PublisherSerializer(serializers.ModelSerializer):
    """Publisher representation with nested editors and journalists."""

    editors = CustomUserSerializer(many=True, read_only=True)
    journalists = CustomUserSerializer(many=True, read_only=True)

    class Meta:
        model = Publisher
        fields = ("id", "name", "description", "editors", "journalists")


class ArticleSerializer(serializers.ModelSerializer):
    """Article representation with nested author + publisher info.

    `author` is read-only and always set server-side from the
    request user — we don't trust client-supplied authorship.
    `publisher` accepts a publisher ID on write (so the journalist
    can choose) but renders the publisher's name on read.
    """

    author = CustomUserSerializer(read_only=True)
    publisher_name = serializers.CharField(
        source="publisher.name",
        read_only=True,
    )

    class Meta:
        model = Article
        fields = (
            "id",
            "title",
            "content",
            "author",
            "publisher",
            "publisher_name",
            "created_at",
            "approved",
        )
        read_only_fields = ("author", "created_at", "approved")


class NewsletterSerializer(serializers.ModelSerializer):
    author = CustomUserSerializer(read_only=True)
    publisher_name = serializers.CharField(
        source="publisher.name",
        read_only=True,
    )

    class Meta:
        model = Newsletter
        fields = (
            "id",
            "title",
            "description",
            "author",
            "publisher",
            "publisher_name",
            "articles",
            "created_at",
        )
        read_only_fields = ("author", "created_at")
