"""Views for the news app.

Organised by concern:
  - Auth views (register; login/logout are Django's built-ins)
  - Article views (list, detail, create, update, delete, approve)
  - Newsletter views (list, detail, create, update, delete)
  - Home page
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import RegistrationForm
from .models import Article, Newsletter, Publisher

# ---------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------


def register(request):
    """Sign-up view. Creates a user, logs them in, and redirects home."""
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f"Welcome, {user.username}! Your account is ready.",
            )
            return redirect("home")
    else:
        form = RegistrationForm()
    return render(request, "registration/register.html", {"form": form})


# ---------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------


def home(request):
    """Landing page — shows the 5 most recent approved articles."""
    latest_articles = Article.objects.filter(approved=True)[:5]
    return render(request, "news/home.html", {"latest_articles": latest_articles})


# ---------------------------------------------------------------------
# Article views
# ---------------------------------------------------------------------


class ArticleListView(ListView):
    """List all approved articles. Readers see only their subscriptions
    if they're logged in as a reader; everyone else sees all approved."""

    model = Article
    template_name = "news/article_list.html"
    context_object_name = "articles"
    paginate_by = 10

    def get_queryset(self):
        """Visibility rules:
        - Editors see everything (approved + pending) so they can
            review submissions.
        - Journalists see approved articles PLUS their own pending
            drafts, so they can keep working on them.
        - Readers see only approved articles, filtered to their
            subscriptions if they have any.
        - Anonymous visitors see only approved articles.
        """
        user = self.request.user

        # Editors see the full list.
        if user.is_authenticated and user.is_editor():
            return Article.objects.all()

        # Journalists: approved articles + their own drafts.
        if user.is_authenticated and user.is_journalist():
            return Article.objects.filter(approved=True) | Article.objects.filter(
                author=user
            )

        # Readers with subscriptions: only their subscribed content.
        if user.is_authenticated and user.is_reader():
            qs = Article.objects.filter(approved=True)
            pub_ids = user.subscribed_publishers.values_list("id", flat=True)
            jrn_ids = user.subscribed_journalists.values_list("id", flat=True)
            if pub_ids or jrn_ids:
                qs = qs.filter(publisher_id__in=pub_ids) | qs.filter(
                    author_id__in=jrn_ids
                )
            return qs.distinct()

        # Anonymous / fallback: approved only.
        return Article.objects.filter(approved=True)


class ArticleDetailView(DetailView):
    model = Article
    template_name = "news/article_detail.html"
    context_object_name = "article"

    def get_queryset(self):
        """Editors see anything; journalists see approved + own drafts;
        everyone else sees only approved."""
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and user.is_editor():
            return qs
        if user.is_authenticated and user.is_journalist():
            return qs.filter(approved=True) | qs.filter(author=user)
        return qs.filter(approved=True)


class JournalistRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict access to journalists only."""

    def test_func(self):
        return self.request.user.is_journalist()


class EditorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict access to editors only."""

    def test_func(self):
        return self.request.user.is_editor()


class ArticleCreateView(JournalistRequiredMixin, CreateView):
    model = Article
    template_name = "news/article_form.html"
    fields = ["title", "content", "publisher"]
    success_url = reverse_lazy("article-list")

    def form_valid(self, form):
        # Author is always the current user, never picked from a form.
        form.instance.author = self.request.user
        messages.success(self.request, "Article submitted for review.")
        return super().form_valid(form)


class ArticleUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Article
    template_name = "news/article_form.html"
    fields = ["title", "content", "publisher"]
    success_url = reverse_lazy("article-list")

    def test_func(self):
        article = self.get_object()
        user = self.request.user
        # Editors can edit any article; journalists only their own.
        if user.is_editor():
            return True
        return user.is_journalist() and article.author == user


class ArticleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Article
    template_name = "news/article_confirm_delete.html"
    success_url = reverse_lazy("article-list")

    def test_func(self):
        article = self.get_object()
        user = self.request.user
        if user.is_editor():
            return True
        return user.is_journalist() and article.author == user


# Editor-only approval action ------------------------------------------


@login_required
def approve_article(request, pk):
    """Editor flips an article from unapproved to approved.

    Phase 7 will hook a post_save signal here that emails subscribers
    and posts to X. For now, approval just sets the flag and redirects.
    """
    if not request.user.is_editor():
        messages.error(request, "Only editors can approve articles.")
        return redirect("article-list")

    article = get_object_or_404(Article, pk=pk)
    if request.method == "POST":
        article.approved = True
        article.save()
        messages.success(
            request,
            f"'{article.title}' approved and published.",
        )
        return redirect("editor-dashboard")

    return render(request, "news/article_approve.html", {"article": article})


class EditorDashboardView(EditorRequiredMixin, ListView):
    """Editor's pending-articles dashboard."""

    model = Article
    template_name = "news/editor_dashboard.html"
    context_object_name = "pending_articles"

    def get_queryset(self):
        return Article.objects.filter(approved=False)


class JournalistDashboardView(JournalistRequiredMixin, ListView):
    """Journalist's own-articles dashboard — shows both approved
    and pending articles authored by the current user, giving them
    a single place to manage their drafts."""

    model = Article
    template_name = "news/journalist_dashboard.html"
    context_object_name = "my_articles"

    def get_queryset(self):
        return Article.objects.filter(author=self.request.user).order_by("-created_at")


# ---------------------------------------------------------------------
# Newsletter views (mirror article views, lighter)
# ---------------------------------------------------------------------


class NewsletterListView(ListView):
    model = Newsletter
    template_name = "news/newsletter_list.html"
    context_object_name = "newsletters"
    paginate_by = 10


class NewsletterDetailView(DetailView):
    model = Newsletter
    template_name = "news/newsletter_detail.html"
    context_object_name = "newsletter"


class NewsletterCreateView(JournalistRequiredMixin, CreateView):
    model = Newsletter
    template_name = "news/newsletter_form.html"
    fields = ["title", "description", "publisher", "articles"]
    success_url = reverse_lazy("newsletter-list")

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, "Newsletter created.")
        return super().form_valid(form)


class NewsletterUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Newsletter
    template_name = "news/newsletter_form.html"
    fields = ["title", "description", "publisher", "articles"]
    success_url = reverse_lazy("newsletter-list")

    def test_func(self):
        nl = self.get_object()
        user = self.request.user
        if user.is_editor():
            return True
        return user.is_journalist() and nl.author == user


class NewsletterDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Newsletter
    template_name = "news/newsletter_confirm_delete.html"
    success_url = reverse_lazy("newsletter-list")

    def test_func(self):
        nl = self.get_object()
        user = self.request.user
        if user.is_editor():
            return True
        return user.is_journalist() and nl.author == user


# ---------------------------------------------------------------------
# Publisher views
# ---------------------------------------------------------------------


class PublisherListView(ListView):
    """Public list of all publishers — readers browse to choose
    who to subscribe to; editors use this as the entry point for
    managing publishers."""

    model = Publisher
    template_name = "news/publisher_list.html"
    context_object_name = "publishers"


class PublisherDetailView(DetailView):
    """Single publisher page — shows editors, journalists, and
    recent articles for the publisher."""

    model = Publisher
    template_name = "news/publisher_detail.html"
    context_object_name = "publisher"


class PublisherCreateView(EditorRequiredMixin, CreateView):
    """Editors create publishers."""

    model = Publisher
    template_name = "news/publisher_form.html"
    fields = ["name", "description", "editors", "journalists"]
    success_url = reverse_lazy("publisher-list")

    def form_valid(self, form):
        messages.success(self.request, "Publisher created.")
        return super().form_valid(form)


class PublisherUpdateView(EditorRequiredMixin, UpdateView):
    """Editors edit publishers."""

    model = Publisher
    template_name = "news/publisher_form.html"
    fields = ["name", "description", "editors", "journalists"]
    success_url = reverse_lazy("publisher-list")

    def form_valid(self, form):
        messages.success(self.request, "Publisher updated.")
        return super().form_valid(form)


class PublisherDeleteView(EditorRequiredMixin, DeleteView):
    """Editors delete publishers."""

    model = Publisher
    template_name = "news/publisher_confirm_delete.html"
    success_url = reverse_lazy("publisher-list")
