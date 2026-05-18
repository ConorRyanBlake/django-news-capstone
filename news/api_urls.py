"""URL routes for the REST API (mounted under /api/)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .api_views import (
    ArticleViewSet,
    NewsletterViewSet,
    PublisherViewSet,
)

app_name = "api"

router = DefaultRouter()
router.register(r"articles", ArticleViewSet, basename="article")
router.register(r"newsletters", NewsletterViewSet, basename="newsletter")
router.register(r"publishers", PublisherViewSet, basename="publisher")

urlpatterns = [
    # JWT auth
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Router-generated endpoints
    path("", include(router.urls)),
]
