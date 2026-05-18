"""Signal handlers for the news app.

The only signal we listen to is post_save on Article. When an
article transitions from unapproved to approved, we fan out:
email subscribers + post to X. Both side-effects are isolated
in news.services so they can be mocked in tests.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Article
from .services import email_subscribers_of_article, post_to_x


@receiver(pre_save, sender=Article)
def cache_previous_approved_state(sender, instance, **kwargs):
    """Stash the previous `approved` value onto the instance so the
    post_save handler can detect the *transition* from False to True.

    Without this, we'd fire on every save where approved=True,
    including subsequent edits to an already-approved article.
    """
    if instance.pk:
        try:
            old = Article.objects.get(pk=instance.pk)
            instance._was_approved = old.approved
        except Article.DoesNotExist:
            instance._was_approved = False
    else:
        # Brand-new article — definitely not previously approved.
        instance._was_approved = False


@receiver(post_save, sender=Article)
def notify_on_approval(sender, instance, created, **kwargs):
    """Fan out notifications when an article is newly approved.

    Triggers only on the False -> True transition, so editing an
    already-approved article doesn't re-spam subscribers.
    """
    was_approved = getattr(instance, "_was_approved", False)
    if instance.approved and not was_approved:
        email_subscribers_of_article(instance)
        post_to_x(instance)
