"""Automated tests for the news app.

Coverage matches the capstone PDF checklist:
  - JWT authentication per role
  - Reader can only retrieve subscribed content
  - Journalist can create articles
  - Editor can approve and delete
  - Newsletters behave correctly
  - Signal logic fires correctly on approval (mocked)

Each test class is isolated: setUp creates the users it needs and
Django's TestCase wraps every test in a transaction that rolls back,
so tests don't leak state between each other.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Article, Newsletter, Publisher

User = get_user_model()


# ---------------------------------------------------------------------
# Shared helper: build a small ecosystem of users + content
# ---------------------------------------------------------------------


class APITestBase(APITestCase):
    """Common fixtures used across most test classes.

    Creates one of each role plus a publisher and a couple of articles
    so individual tests don't have to repeat boilerplate.

    All signal side-effects (email + X) are mocked for the entire
    duration of every test so we never hit real third-party services.
    """

    def setUp(self):
        # Start patches BEFORE creating any articles so the signal
        # side-effects are intercepted even during setUp itself.
        # We patch at the location where signals.py imports them.
        self._mail_patch = patch("news.signals.email_subscribers_of_article")
        self._tweet_patch = patch("news.signals.post_to_x")
        self.mock_mail = self._mail_patch.start()
        self.mock_tweet = self._tweet_patch.start()
        self.addCleanup(self._mail_patch.stop)
        self.addCleanup(self._tweet_patch.stop)

        # Users — one per role
        self.reader = User.objects.create_user(
            username="reader1",
            password="pass12345",
            email="reader1@example.com",
            role=User.Role.READER,
        )
        self.journalist = User.objects.create_user(
            username="journo1",
            password="pass12345",
            email="journo1@example.com",
            role=User.Role.JOURNALIST,
        )
        self.other_journalist = User.objects.create_user(
            username="journo2",
            password="pass12345",
            email="journo2@example.com",
            role=User.Role.JOURNALIST,
        )
        self.editor = User.objects.create_user(
            username="editor1",
            password="pass12345",
            email="editor1@example.com",
            role=User.Role.EDITOR,
        )

        # Publisher + journalist affiliation
        self.publisher = Publisher.objects.create(name="Daily Times")
        self.publisher.journalists.add(self.journalist)
        self.publisher.editors.add(self.editor)

        # Articles: one approved, one pending
        self.approved_article = Article.objects.create(
            title="Approved Story",
            content="Body of approved story.",
            author=self.journalist,
            publisher=self.publisher,
            approved=True,
        )
        self.pending_article = Article.objects.create(
            title="Pending Story",
            content="Body of pending story.",
            author=self.journalist,
            publisher=self.publisher,
            approved=False,
        )

    # ---- small helpers ------------------------------------------------

    def authenticate_as(self, user):
        """Obtain a JWT for `user` and attach it to the test client."""
        resp = self.client.post(
            reverse("api:token_obtain_pair"),
            {"username": user.username, "password": "pass12345"},
            format="json",
        )
        self.assertEqual(
            resp.status_code, status.HTTP_200_OK, f"Token endpoint failed: {resp.data}"
        )
        token = resp.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


# ---------------------------------------------------------------------
# 1. JWT authentication
# ---------------------------------------------------------------------


class JWTAuthTests(APITestBase):
    """Verify token issuing and rejection of bad credentials."""

    def test_token_obtain_returns_access_and_refresh(self):
        resp = self.client.post(
            reverse("api:token_obtain_pair"),
            {"username": "reader1", "password": "pass12345"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_token_obtain_rejects_wrong_password(self):
        resp = self.client.post(
            reverse("api:token_obtain_pair"),
            {"username": "reader1", "password": "wrong"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_protected_endpoint_rejects_anonymous(self):
        resp = self.client.get(reverse("api:article-list"))
        # /api/articles/ requires auth
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------
# 2. Role-based GET access
# ---------------------------------------------------------------------


class ArticleListByRoleTests(APITestBase):
    """Each role should see the right slice of articles."""

    def test_reader_sees_only_approved_articles(self):
        self.authenticate_as(self.reader)
        resp = self.client.get(reverse("api:article-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        titles = [a["title"] for a in resp.data["results"]]
        self.assertIn("Approved Story", titles)
        self.assertNotIn("Pending Story", titles)

    def test_journalist_sees_approved_plus_own_drafts(self):
        self.authenticate_as(self.journalist)
        resp = self.client.get(reverse("api:article-list"))
        titles = [a["title"] for a in resp.data["results"]]
        # Approved is visible to everyone; the journalist's own
        # pending article is also visible to its author.
        self.assertIn("Approved Story", titles)
        self.assertIn("Pending Story", titles)

    def test_other_journalist_does_not_see_someone_elses_draft(self):
        self.authenticate_as(self.other_journalist)
        resp = self.client.get(reverse("api:article-list"))
        titles = [a["title"] for a in resp.data["results"]]
        self.assertIn("Approved Story", titles)
        self.assertNotIn("Pending Story", titles)

    def test_editor_sees_all_articles_including_pending(self):
        self.authenticate_as(self.editor)
        resp = self.client.get(reverse("api:article-list"))
        titles = [a["title"] for a in resp.data["results"]]
        self.assertIn("Approved Story", titles)
        self.assertIn("Pending Story", titles)


# ---------------------------------------------------------------------
# 3. Reader subscription filtering
# ---------------------------------------------------------------------


class ReaderSubscriptionTests(APITestBase):
    """The /subscribed/ endpoint returns only content from the
    reader's subscribed publishers and journalists."""

    def setUp(self):
        super().setUp()
        # A second publisher + a second approved article that the
        # reader is NOT subscribed to.
        self.other_publisher = Publisher.objects.create(name="Other Press")
        self.other_publisher.journalists.add(self.other_journalist)
        self.unsubscribed_article = Article.objects.create(
            title="Unsubscribed Story",
            content="...",
            author=self.other_journalist,
            publisher=self.other_publisher,
            approved=True,
        )

    def test_reader_subscribed_endpoint_returns_only_subscriptions(self):
        # Subscribe reader to the Daily Times only.
        self.reader.subscribed_publishers.add(self.publisher)
        self.authenticate_as(self.reader)

        resp = self.client.get(reverse("api:article-subscribed"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        titles = [a["title"] for a in resp.data["results"]]
        self.assertIn("Approved Story", titles)  # Daily Times
        self.assertNotIn("Unsubscribed Story", titles)  # Other Press

    def test_reader_with_journalist_subscription_only(self):
        # Subscribe to the journalist, not the publisher.
        self.reader.subscribed_journalists.add(self.journalist)
        self.authenticate_as(self.reader)

        resp = self.client.get(reverse("api:article-subscribed"))
        titles = [a["title"] for a in resp.data["results"]]
        self.assertIn("Approved Story", titles)
        self.assertNotIn("Unsubscribed Story", titles)

    def test_reader_with_no_subscriptions_gets_empty_list(self):
        self.authenticate_as(self.reader)
        resp = self.client.get(reverse("api:article-subscribed"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # paginated empty result
        self.assertEqual(len(resp.data["results"]), 0)


# ---------------------------------------------------------------------
# 4. Journalist creates articles
# ---------------------------------------------------------------------


class JournalistCreateTests(APITestBase):
    """Only journalists can POST; the author is auto-set."""

    def _payload(self):
        return {
            "title": "Fresh Take",
            "content": "Some original reporting.",
            "publisher": self.publisher.id,
        }

    def test_journalist_can_create_article(self):
        self.authenticate_as(self.journalist)
        resp = self.client.post(
            reverse("api:article-list"),
            self._payload(),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Author auto-set to the current user, not whatever the
        # client might have tried to inject.
        self.assertEqual(resp.data["author"]["username"], self.journalist.username)
        # New articles start unapproved regardless of payload.
        self.assertFalse(resp.data["approved"])

    def test_reader_cannot_create_article(self):
        self.authenticate_as(self.reader)
        resp = self.client.post(
            reverse("api:article-list"),
            self._payload(),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_cannot_create_article(self):
        # PDF says only journalists POST. Editors approve, they
        # don't write.
        self.authenticate_as(self.editor)
        resp = self.client.post(
            reverse("api:article-list"),
            self._payload(),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_create_article(self):
        resp = self.client.post(
            reverse("api:article-list"),
            self._payload(),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------
# 5. Editor approves and deletes
# ---------------------------------------------------------------------


class EditorActionsTests(APITestBase):
    """Editors can approve and delete articles."""

    def test_editor_can_approve_article(self):
        # Reset the mock counters that fired during setUp's creation
        # of the approved article, so this test asserts cleanly on
        # the new approval triggered here.
        self.mock_mail.reset_mock()
        self.mock_tweet.reset_mock()

        self.authenticate_as(self.editor)
        resp = self.client.post(
            reverse("api:article-approve", args=[self.pending_article.id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.pending_article.refresh_from_db()
        self.assertTrue(self.pending_article.approved)
        # Signal fired the side-effects exactly once
        self.mock_mail.assert_called_once()
        self.mock_tweet.assert_called_once()

    def test_approving_already_approved_article_returns_400(self):
        self.authenticate_as(self.editor)
        resp = self.client.post(
            reverse("api:article-approve", args=[self.approved_article.id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_journalist_cannot_approve(self):
        self.authenticate_as(self.journalist)
        resp = self.client.post(
            reverse("api:article-approve", args=[self.pending_article.id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_reader_cannot_approve(self):
        self.authenticate_as(self.reader)
        resp = self.client.post(
            reverse("api:article-approve", args=[self.pending_article.id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_delete_any_article(self):
        self.authenticate_as(self.editor)
        resp = self.client.delete(
            reverse("api:article-detail", args=[self.pending_article.id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Article.objects.filter(id=self.pending_article.id).exists())

    def test_journalist_can_delete_own_article(self):
        self.authenticate_as(self.journalist)
        resp = self.client.delete(
            reverse("api:article-detail", args=[self.pending_article.id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_journalist_cannot_delete_others_article(self):
        self.authenticate_as(self.other_journalist)

        # Case 1: pending article authored by someone else.
        # Hidden by queryset filtering -> 404.
        resp = self.client.delete(
            reverse("api:article-detail", args=[self.pending_article.id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        # Case 2: approved article authored by someone else.
        # Visible in the queryset, so the permission class runs and
        # correctly returns 403.
        resp = self.client.delete(
            reverse("api:article-detail", args=[self.approved_article.id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------
# 6. Newsletters
# ---------------------------------------------------------------------


class NewsletterTests(APITestBase):
    """Newsletters: list, journalist can create, editor can edit/delete."""

    def setUp(self):
        super().setUp()
        self.newsletter = Newsletter.objects.create(
            title="Weekly Digest",
            description="Roundup of the week.",
            author=self.journalist,
            publisher=self.publisher,
        )
        self.newsletter.articles.add(self.approved_article)

    def test_anyone_authenticated_can_list_newsletters(self):
        self.authenticate_as(self.reader)
        resp = self.client.get(reverse("api:newsletter-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        titles = [n["title"] for n in resp.data["results"]]
        self.assertIn("Weekly Digest", titles)

    def test_journalist_can_create_newsletter(self):
        self.authenticate_as(self.journalist)
        resp = self.client.post(
            reverse("api:newsletter-list"),
            {
                "title": "Monthly Recap",
                "description": "End of month roundup.",
                "publisher": self.publisher.id,
                "articles": [self.approved_article.id],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            resp.data["author"]["username"],
            self.journalist.username,
        )

    def test_reader_cannot_create_newsletter(self):
        self.authenticate_as(self.reader)
        resp = self.client.post(
            reverse("api:newsletter-list"),
            {
                "title": "X",
                "description": "Y",
                "publisher": self.publisher.id,
                "articles": [],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_delete_newsletter(self):
        self.authenticate_as(self.editor)
        resp = self.client.delete(
            reverse("api:newsletter-detail", args=[self.newsletter.id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------
# 7. Signal logic — verify the @receiver fires correctly
# ---------------------------------------------------------------------


class SignalLogicTests(APITestBase):
    """Approval signal fans out correctly.

    The service functions are mocked globally in APITestBase.setUp,
    so we just inspect the mocks directly to count calls.
    """

    def test_signal_fires_on_false_to_true_transition(self):
        self.mock_mail.reset_mock()
        self.mock_tweet.reset_mock()

        self.pending_article.approved = True
        self.pending_article.save()

        self.mock_mail.assert_called_once_with(self.pending_article)
        self.mock_tweet.assert_called_once_with(self.pending_article)

    def test_signal_does_not_fire_on_subsequent_save(self):
        # First, approve it (fires signals — but we don't care here).
        self.pending_article.approved = True
        self.pending_article.save()
        self.mock_mail.reset_mock()
        self.mock_tweet.reset_mock()

        # Now save it again as already-approved — no fan-out.
        self.pending_article.title = "Edited title"
        self.pending_article.save()
        self.mock_mail.assert_not_called()
        self.mock_tweet.assert_not_called()

    def test_signal_does_not_fire_when_creating_unapproved_article(self):
        self.mock_mail.reset_mock()
        self.mock_tweet.reset_mock()

        Article.objects.create(
            title="New draft",
            content="Body",
            author=self.journalist,
            publisher=self.publisher,
            approved=False,
        )
        self.mock_mail.assert_not_called()
        self.mock_tweet.assert_not_called()


# ---------------------------------------------------------------------
# 8. Resubmission additions — Publisher CRUD + Journalist Dashboard
# ---------------------------------------------------------------------


class PublisherFrontEndTests(APITestBase):
    """Publishers can be managed from the front end by editors;
    readers/journalists can view but not modify."""

    def test_anyone_authenticated_can_view_publisher_list(self):
        self.client.force_login(self.reader)
        resp = self.client.get(reverse("publisher-list"))
        self.assertEqual(resp.status_code, 200)

    def test_editor_can_create_publisher(self):
        self.client.force_login(self.editor)
        resp = self.client.post(
            reverse("publisher-create"),
            {"name": "New Press", "description": "A new outlet."},
        )
        # Redirects on success
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Publisher.objects.filter(name="New Press").exists())

    def test_journalist_cannot_create_publisher(self):
        self.client.force_login(self.journalist)
        resp = self.client.post(
            reverse("publisher-create"),
            {"name": "Should Fail", "description": "..."},
        )
        # UserPassesTestMixin returns 403
        self.assertEqual(resp.status_code, 403)

    def test_reader_cannot_create_publisher(self):
        self.client.force_login(self.reader)
        resp = self.client.post(
            reverse("publisher-create"),
            {"name": "Should Fail", "description": "..."},
        )
        self.assertEqual(resp.status_code, 403)


class JournalistDashboardTests(APITestBase):
    """The journalist dashboard lists the user's own articles
    including drafts."""

    def test_journalist_sees_own_drafts_on_dashboard(self):
        self.client.force_login(self.journalist)
        resp = self.client.get(reverse("journalist-dashboard"))
        self.assertEqual(resp.status_code, 200)
        # The pending_article from setUp is by this journalist
        self.assertContains(resp, "Pending Story")
        self.assertContains(resp, "Approved Story")

    def test_journalist_does_not_see_other_journalists_articles(self):
        self.client.force_login(self.other_journalist)
        resp = self.client.get(reverse("journalist-dashboard"))
        # other_journalist has no articles in setUp
        self.assertNotContains(resp, "Pending Story")
        self.assertNotContains(resp, "Approved Story")

    def test_journalist_can_edit_own_draft(self):
        """Explicit verification of the mentor's main point:
        journalists must be able to edit unapproved drafts."""
        self.client.force_login(self.journalist)
        resp = self.client.get(
            reverse("article-update", args=[self.pending_article.pk])
        )
        self.assertEqual(resp.status_code, 200)

    def test_reader_cannot_access_journalist_dashboard(self):
        self.client.force_login(self.reader)
        resp = self.client.get(reverse("journalist-dashboard"))
        # JournalistRequiredMixin returns 403
        self.assertEqual(resp.status_code, 403)

    def test_journalist_sees_own_drafts_in_article_list(self):
        """The standard /articles/ page should include the journalist's
        own pending drafts, not just approved articles."""
        self.client.force_login(self.journalist)
        resp = self.client.get(reverse("article-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Pending Story")
        self.assertContains(resp, "Approved Story")

    def test_journalist_can_view_own_draft_detail(self):
        """Clicking through to a draft from any list should work,
        not 404."""
        self.client.force_login(self.journalist)
        resp = self.client.get(
            reverse("article-detail", args=[self.pending_article.pk])
        )
        self.assertEqual(resp.status_code, 200)
