"""Models for the news application.

Defines the custom user model with role-based fields, plus Publisher,
Article, and Newsletter models.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Custom user model with a role field and subscription relations.

    Three roles are supported: reader, journalist, editor. The role
    determines which Django Group the user is assigned to and which
    custom fields are meaningful for the user.

    Reader-only fields (subscribed_publishers, subscribed_journalists)
    are kept blank for non-readers. Journalist content is stored as
    reverse relations on the Article and Newsletter models.
    """

    class Role(models.TextChoices):
        READER = "reader", "Reader"
        JOURNALIST = "journalist", "Journalist"
        EDITOR = "editor", "Editor"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.READER,
    )

    # Reader-only subscription fields.
    subscribed_publishers = models.ManyToManyField(
        "Publisher",
        related_name="reader_subscribers",
        blank=True,
    )
    subscribed_journalists = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="journalist_subscribers",
        blank=True,
    )

    # Role-check helpers used in views, templates, and permissions.
    def is_reader(self):
        return self.role == self.Role.READER

    def is_journalist(self):
        return self.role == self.Role.JOURNALIST

    def is_editor(self):
        return self.role == self.Role.EDITOR

    def save(self, *args, **kwargs):
        """Save the user, then sync their Django group to match their role.

        Each role corresponds to a group of the same name (created by
        the 0002_create_role_groups data migration). Whenever the user
        is saved, we remove them from the other two role groups and
        add them to the one matching their current role. This means
        role changes via the admin or registration form are reflected
        in group membership and therefore permissions.
        """
        # Save first so the user has a primary key for M2M operations.
        super().save(*args, **kwargs)

        # Import locally to avoid circular imports at module load time.
        from django.contrib.auth.models import Group

        role_to_group = {
            self.Role.READER: "Reader",
            self.Role.JOURNALIST: "Journalist",
            self.Role.EDITOR: "Editor",
        }

        target_group_name = role_to_group.get(self.role)
        if not target_group_name:
            return

        # Remove from any other role groups, then add to the right one.
        other_groups = [
            name for name in role_to_group.values() if name != target_group_name
        ]
        self.groups.remove(*Group.objects.filter(name__in=other_groups))
        target_group = Group.objects.filter(name=target_group_name).first()
        if target_group:
            self.groups.add(target_group)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Publisher(models.Model):
    """A publication house that hosts editors and journalists.

    A single user can be an editor or journalist for multiple
    publishers (M2M on both sides).
    """

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    editors = models.ManyToManyField(
        "CustomUser",
        related_name="publishers_as_editor",
        limit_choices_to={"role": "editor"},
        blank=True,
    )
    journalists = models.ManyToManyField(
        "CustomUser",
        related_name="publishers_as_journalist",
        limit_choices_to={"role": "journalist"},
        blank=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Article(models.Model):
    """An article authored by a journalist.

    Articles can either be tied to a publisher (publisher content)
    or independent (publisher is null). Articles must be approved by
    an editor before being visible to readers — the approved flag
    drives a post_save signal that emails subscribers and posts to X.
    """

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(
        "CustomUser",
        on_delete=models.CASCADE,
        related_name="articles",
        limit_choices_to={"role": "journalist"},
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        related_name="articles",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Newsletter(models.Model):
    """A curated collection of articles produced by a journalist.

    Like Article, a newsletter may be tied to a publisher or remain
    independent. The articles field is the curated set.
    """

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    author = models.ForeignKey(
        "CustomUser",
        on_delete=models.CASCADE,
        related_name="newsletters",
        limit_choices_to={"role": "journalist"},
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        related_name="newsletters",
        null=True,
        blank=True,
    )
    articles = models.ManyToManyField(
        Article,
        related_name="newsletters",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
