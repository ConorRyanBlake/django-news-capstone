"""URL routes for the news app."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    # Articles
    path("articles/", views.ArticleListView.as_view(), name="article-list"),
    path("articles/new/", views.ArticleCreateView.as_view(), name="article-create"),
    path(
        "articles/<int:pk>/", views.ArticleDetailView.as_view(), name="article-detail"
    ),
    path(
        "articles/<int:pk>/edit/",
        views.ArticleUpdateView.as_view(),
        name="article-update",
    ),
    path(
        "articles/<int:pk>/delete/",
        views.ArticleDeleteView.as_view(),
        name="article-delete",
    ),
    path("articles/<int:pk>/approve/", views.approve_article, name="article-approve"),
    # Editor dashboard
    path("editor/", views.EditorDashboardView.as_view(), name="editor-dashboard"),
    path(
        "journalist/",
        views.JournalistDashboardView.as_view(),
        name="journalist-dashboard",
    ),
    # Newsletters
    path("newsletters/", views.NewsletterListView.as_view(), name="newsletter-list"),
    path(
        "newsletters/new/",
        views.NewsletterCreateView.as_view(),
        name="newsletter-create",
    ),
    path(
        "newsletters/<int:pk>/",
        views.NewsletterDetailView.as_view(),
        name="newsletter-detail",
    ),
    path(
        "newsletters/<int:pk>/edit/",
        views.NewsletterUpdateView.as_view(),
        name="newsletter-update",
    ),
    path(
        "newsletters/<int:pk>/delete/",
        views.NewsletterDeleteView.as_view(),
        name="newsletter-delete",
    ),
    # Publishers
    path("publishers/", views.PublisherListView.as_view(), name="publisher-list"),
    path(
        "publishers/new/", views.PublisherCreateView.as_view(), name="publisher-create"
    ),
    path(
        "publishers/<int:pk>/",
        views.PublisherDetailView.as_view(),
        name="publisher-detail",
    ),
    path(
        "publishers/<int:pk>/edit/",
        views.PublisherUpdateView.as_view(),
        name="publisher-update",
    ),
    path(
        "publishers/<int:pk>/delete/",
        views.PublisherDeleteView.as_view(),
        name="publisher-delete",
    ),
]
