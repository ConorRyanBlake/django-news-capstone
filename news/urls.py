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
]
