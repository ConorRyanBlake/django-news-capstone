"""Admin registrations for the news app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Article, CustomUser, Newsletter, Publisher


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin for CustomUser, extending Django's default UserAdmin
    so all built-in user features (password change, permissions,
    group assignment) still work, plus our role and subscription
    fields are visible."""

    list_display = (
        "username",
        "email",
        "role",
        "is_staff",
        "is_active",
    )
    list_filter = ("role", "is_staff", "is_active")

    # Add our custom fields to the existing UserAdmin fieldsets.
    fieldsets = UserAdmin.fieldsets + (
        (
            "Role & subscriptions",
            {
                "fields": (
                    "role",
                    "subscribed_publishers",
                    "subscribed_journalists",
                ),
            },
        ),
    )
    # Same for the "add user" page.
    add_fieldsets = UserAdmin.add_fieldsets + (("Role", {"fields": ("role",)}),)


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    filter_horizontal = ("editors", "journalists")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "publisher", "approved", "created_at")
    list_filter = ("approved", "publisher", "created_at")
    search_fields = ("title", "content")
    list_editable = ("approved",)  # toggle approval from the list view


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "publisher", "created_at")
    list_filter = ("publisher", "created_at")
    search_fields = ("title", "description")
    filter_horizontal = ("articles",)
