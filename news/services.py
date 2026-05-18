"""External-service helpers for the news app.

Each function is a small wrapper around an external integration
(X/Twitter, email). Wrapping them here keeps signal handlers and
views focused on business logic, and makes the integrations
easy to mock in tests.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

# import sys


def post_to_x(article):
    """Post a tweet announcing the approval of an article.

    Returns the response from the X API on success, or None if X
    credentials are missing or the call fails. Failures are
    deliberately swallowed so that a flaky third-party API never
    crashes the approval workflow. Outcomes are printed to the
    terminal so the developer can see what happened during a real
    approval (success, skipped, or which error came back).
    """
    # Skip entirely when running the test suite. Tests that want
    # to assert this function was called should patch it explicitly.
    # if "test" in sys.argv:
    #     return None

    # Late import so tweepy isn't required at module load time.
    try:
        import tweepy
    except ImportError:
        print("[X] tweepy not installed — skipping tweet.")
        return None

    if not all(
        [
            settings.X_API_KEY,
            settings.X_API_SECRET,
            settings.X_ACCESS_TOKEN,
            settings.X_ACCESS_TOKEN_SECRET,
        ]
    ):
        print("[X] No credentials configured — skipping tweet.")
        return None

    article_url = (
        f"{settings.SITE_BASE_URL}" f"{reverse('article-detail', args=[article.pk])}"
    )
    tweet_text = (
        f"New article: {article.title}\n"
        f"By {article.author.username}"
        f"{' for ' + article.publisher.name if article.publisher else ''}"
        f"\n{article_url}"
    )
    tweet_text = tweet_text[:280]

    try:
        client = tweepy.Client(
            consumer_key=settings.X_API_KEY,
            consumer_secret=settings.X_API_SECRET,
            access_token=settings.X_ACCESS_TOKEN,
            access_token_secret=settings.X_ACCESS_TOKEN_SECRET,
        )
        response = client.create_tweet(text=tweet_text)
        print(f"[X] Tweet posted successfully: id={response.data['id']}")
        return response
    except Exception as exc:
        # Surface the error class and message so we can tell rate-limit
        # vs auth vs network issues apart, without breaking approval.
        print(f"[X] Tweet failed ({type(exc).__name__}): {exc}")
        return None


def email_subscribers_of_article(article):
    """Email everyone subscribed to the article's publisher or author.

    Subscribers are CustomUsers with the Reader role whose
    subscribed_publishers or subscribed_journalists relations
    include this article's publisher or author respectively.
    Returns the number of recipients emailed (0 if none).
    """
    # Skip entirely when running the test suite. Tests that want
    # to assert this function was called should patch it explicitly.
    # if "test" in sys.argv:
    #     return None

    # Build the set of recipient emails.
    # Using a set deduplicates anyone subscribed to both the publisher
    # and the journalist for the same article.
    recipients = set()

    # Subscribers via publisher
    if article.publisher is not None:
        for reader in article.publisher.reader_subscribers.all():
            if reader.email:
                recipients.add(reader.email)

    # Subscribers via journalist
    for reader in article.author.journalist_subscribers.all():
        if reader.email:
            recipients.add(reader.email)

    if not recipients:
        print(f"[Email] No subscribers for '{article.title}' — " f"nothing to send.")
        return 0

    article_url = (
        f"{settings.SITE_BASE_URL}" f"{reverse('article-detail', args=[article.pk])}"
    )
    subject = f"New article published: {article.title}"
    message = (
        f"Hi,\n\n"
        f"A new article you may be interested in has been published:\n\n"
        f"Title: {article.title}\n"
        f"Author: {article.author.username}"
        f"{' (' + article.publisher.name + ')' if article.publisher else ''}"
        f"\n\n"
        f"Read it here: {article_url}\n\n"
        f"— News Platform"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=list(recipients),
        fail_silently=True,
    )
    print(
        f"[Email] Sent article '{article.title}' to "
        f"{len(recipients)} subscriber(s)."
    )
    return len(recipients)
