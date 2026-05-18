"""Data migration: create Reader, Editor, and Journalist groups
and assign the permissions required by the project spec.

This runs once when migrations are applied, so groups exist
out-of-the-box for any developer cloning the repo.
"""

from django.db import migrations

# Permissions per role. Codenames follow Django's default naming:
# add_<model>, view_<model>, change_<model>, delete_<model>.
ROLE_PERMISSIONS = {
    "Reader": [
        "view_article",
        "view_newsletter",
    ],
    "Editor": [
        "view_article",
        "change_article",
        "delete_article",
        "view_newsletter",
        "change_newsletter",
        "delete_newsletter",
    ],
    "Journalist": [
        "add_article",
        "view_article",
        "change_article",
        "delete_article",
        "add_newsletter",
        "view_newsletter",
        "change_newsletter",
        "delete_newsletter",
    ],
}


def create_groups(apps, schema_editor):
    """Create the three role groups and attach their permissions."""
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for group_name, codenames in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        # Look up each permission by codename and attach it.
        # We filter by codename__in to do it in a single query.
        perms = Permission.objects.filter(codename__in=codenames)
        group.permissions.set(perms)


def remove_groups(apps, schema_editor):
    """Reverse the migration by deleting the three groups."""
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLE_PERMISSIONS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
