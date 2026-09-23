"""
Shared permission classes.

The platform has a small number of standing capabilities (see
forge.accounts.models.PlatformRole) and a larger number of per-object
relationships -- project lead, team member, assigned mentor. Standing
capabilities live here; relationship checks live next to the model they
concern, because that is where a maintainer will look for them.
"""

from __future__ import annotations

from rest_framework import permissions


class IsVerifiedStudent(permissions.BasePermission):
    """
    The baseline for participation.

    Only a person whose University email has been verified -- or who arrived
    through University single sign-on -- may act on FORGE. Reading some public
    surfaces (showcase, a public portfolio) does not require this; writing
    anything always does.
    """

    message = "Verify your University email address before taking this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_verified_member)


class IsSelfOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj == request.user or getattr(obj, "user_id", None) == request.user.id


class IsAuthorOrReadOnly(permissions.BasePermission):
    author_field = "author"

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        author_field = getattr(view, "author_field", self.author_field)
        return getattr(obj, f"{author_field}_id", None) == request.user.id


class HasPlatformRole(permissions.BasePermission):
    """
    Grants access to holders of a standing role.

    Set `required_roles` on the view. A superuser always passes -- the
    Directorate of ICT needs a way in that does not depend on the platform's
    own role table being correct.
    """

    message = "This action is restricted to platform stewards."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        required = set(getattr(view, "required_roles", ()) or ())
        if not required:
            return True
        return bool(required & set(user.role_names))


class IsModerator(HasPlatformRole):
    message = "This action is restricted to moderators and community leads."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.is_superuser or user.can_moderate


class IsMentorOrLead(permissions.BasePermission):
    message = "Only a faculty mentor or a community lead may review proposals."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.is_superuser or user.can_review_proposals


class ReadOnly(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.method in permissions.SAFE_METHODS
