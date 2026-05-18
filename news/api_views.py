"""DRF viewsets for the news app's REST API.

The PDF requires six article endpoints. We provide them by combining
DRF's ModelViewSet (which gives us list/retrieve/create/update/destroy
out of the box) with a custom `subscribed` action and an `approve`
action. Newsletter and Publisher get plain read-only and full viewsets
respectively.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Article, Newsletter, Publisher
from .permissions import (
    IsAuthorOrEditorOrReadOnly,
    IsEditor,
    IsJournalistOrReadOnly,
)
from .serializers import (
    ArticleSerializer,
    NewsletterSerializer,
    PublisherSerializer,
)


class ArticleViewSet(viewsets.ModelViewSet):
    """Articles API.

    Routes provided by DRF's router (see api_urls.py):
        GET    /api/articles/             list approved articles
        POST   /api/articles/             create (journalists only)
        GET    /api/articles/<id>/        retrieve
        PUT    /api/articles/<id>/        update (author or editor)
        PATCH  /api/articles/<id>/        partial update
        DELETE /api/articles/<id>/        delete (author or editor)
    Custom actions:
        GET    /api/articles/subscribed/  reader's subscriptions
        POST   /api/articles/<id>/approve/  editor approves
    """

    serializer_class = ArticleSerializer
    permission_classes = [
        IsAuthenticated,
        IsJournalistOrReadOnly,
        IsAuthorOrEditorOrReadOnly,
    ]

    def get_queryset(self):
        """Editors see everything (approved + pending) so they can
        review. Everyone else sees only approved articles. Journalists
        additionally see their own unapproved drafts."""
        user = self.request.user
        qs = Article.objects.all().order_by("-created_at")
        if user.is_authenticated and user.is_editor():
            return qs
        if user.is_authenticated and user.is_journalist():
            # Journalist sees approved articles + their own drafts.
            return qs.filter(approved=True) | qs.filter(author=user)
        # Reader / anonymous / fallback: approved only.
        return qs.filter(approved=True)

    def perform_create(self, serializer):
        """Author is always the current user, never trusted from
        the request body."""
        serializer.save(author=self.request.user)

    @action(
        detail=False,
        methods=["get"],
        url_path="subscribed",
        permission_classes=[IsAuthenticated],
    )
    def subscribed(self, request):
        """GET /api/articles/subscribed/

        Returns approved articles from the reader's subscribed
        publishers and journalists. Non-readers get an empty list
        (the endpoint is meaningful only for readers).
        """
        user = request.user
        if not user.is_reader():
            return Response([])

        pub_ids = user.subscribed_publishers.values_list("id", flat=True)
        jrn_ids = user.subscribed_journalists.values_list("id", flat=True)

        qs = Article.objects.filter(approved=True).filter(
            # Either it's by a subscribed publisher
            # or it's by a subscribed journalist.
            publisher_id__in=list(pub_ids)
        ) | Article.objects.filter(approved=True).filter(author_id__in=list(jrn_ids))
        qs = qs.distinct().order_by("-created_at")

        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(ArticleSerializer(page, many=True).data)
        return Response(ArticleSerializer(qs, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="approve",
        permission_classes=[IsAuthenticated, IsEditor],
    )
    def approve(self, request, pk=None):
        """POST /api/articles/<id>/approve/

        Editor-only. Flips approved=True, which triggers the
        post_save signal to email subscribers and post to X.
        """
        article = get_object_or_404(Article, pk=pk)
        if article.approved:
            return Response(
                {"detail": "Article is already approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        article.approved = True
        article.save()
        return Response(ArticleSerializer(article).data)


class NewsletterViewSet(viewsets.ModelViewSet):
    """Newsletters API. Same role logic as articles, minus approval
    (the PDF doesn't require newsletter approval)."""

    queryset = Newsletter.objects.all().order_by("-created_at")
    serializer_class = NewsletterSerializer
    permission_classes = [
        IsAuthenticated,
        IsJournalistOrReadOnly,
        IsAuthorOrEditorOrReadOnly,
    ]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class PublisherViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only publishers API — for clients listing what publishers
    they can subscribe to. Creation/editing of publishers is left
    to the Django admin in this iteration."""

    queryset = Publisher.objects.all().order_by("name")
    serializer_class = PublisherSerializer
    permission_classes = [IsAuthenticated]
