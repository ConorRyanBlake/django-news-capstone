"""App config for the news app."""

from django.apps import AppConfig


class NewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "news"

    def ready(self):
        # Import signals so the @receiver decorators register them
        # with Django's signal dispatcher. Must be done here, after
        # apps are loaded, to avoid circular import issues.
        from . import signals  # noqa: F401
