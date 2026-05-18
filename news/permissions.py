"""Custom DRF permission classes for role-based API access.

DRF's permission classes have two methods: has_permission (general
access to the endpoint) and has_object_permission (access to a
specific row). We use both to enforce the PDF's rules:

  - Only journalists can POST.
  - Only editors can approve.
  - Readers can only view.
  - Authors can edit/delete their own work; editors can edit/delete
    anyone's.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsJournalistOrReadOnly(BasePermission):
    """Allow safe methods (GET/HEAD/OPTIONS) for anyone authenticated;
    POST is restricted to journalists only."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        # Write actions (POST/PUT/PATCH/DELETE)
        if request.method == "POST":
            return request.user.is_authenticated and request.user.is_journalist()
        # PUT/PATCH/DELETE — fall through to object-level check.
        return request.user.is_authenticated


class IsAuthorOrEditorOrReadOnly(BasePermission):
    """Row-level: only the article's author (if journalist) or any
    editor can update or delete. Everyone else gets read-only."""

    def has_object_permission(self, request, view, obj):
        """Row-level permission check.

        DRF's signature is (self, request, view, obj) — `obj` is the
        model instance being accessed. SAFE methods (GET/HEAD/OPTIONS)
        are allowed; mutations require either editor rights or
        journalist-ownership.
        """
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_editor():
            return True
        if user.is_journalist() and obj.author_id == user.id:
            return True
        return False


class IsEditor(BasePermission):
    """Editor-only endpoints (article approval)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_editor()
