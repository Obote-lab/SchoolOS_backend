from django.conf import settings
from rest_framework.permissions import BasePermission

def get_user_type(user):
    return getattr(user, "user_type", None)


def is_system_root(user):
    return (
        user.is_authenticated
        and get_user_type(user) == "SYS"
    )


def get_managed_county_ids(user):
    """
    Return IDs of counties managed by a Regional Admin.
    """

    counties = getattr(user, "managed_counties", None)

    if counties is None:
        return set()

    return {
        str(county_id)
        for county_id in counties.values_list("pk", flat=True)
    }


def get_school_id(user):
    school = getattr(user, "school", None)

    if not school:
        return None

    return str(school.pk)


def can_view_article(user, article):
    if not user or not user.is_authenticated:
        return False

    if is_system_root(user):
        return True

    if article.status != article.Status.PUBLISHED:
        return False

    if (
        article.audience_roles
        and get_user_type(user) not in article.audience_roles
    ):
        return False

    if article.scope == article.Scope.GLOBAL:
        return True

    if article.scope == article.Scope.REGIONAL:
        if get_user_type(user) != "RAD":
            return False

        return article.scope_key in get_managed_county_ids(user)

    if article.scope == article.Scope.SCHOOL:
        return article.scope_key == get_school_id(user)

    return False


def can_manage_article(user, article):
    if not user or not user.is_authenticated:
        return False

    if is_system_root(user):
        return True

    manager_types = getattr(
        settings,
        "DOCUMENTATION_MANAGER_USER_TYPES",
        ["RAD", "ADM"],
    )

    if get_user_type(user) not in manager_types:
        return False

    if article.scope == article.Scope.GLOBAL:
        return False

    if article.scope == article.Scope.REGIONAL:
        if get_user_type(user) != "RAD":
            return False

        return article.scope_key in get_managed_county_ids(user)

    if article.scope == article.Scope.SCHOOL:
        if get_user_type(user) == "RAD":
            return False

        return article.scope_key == get_school_id(user)

    return False


class CanManageDocumentation(BasePermission):
    """
    Permission for creating documentation.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if is_system_root(user):
            return True

        manager_types = getattr(
            settings,
            "DOCUMENTATION_MANAGER_USER_TYPES",
            ["RAD", "ADM"],
        )

        return get_user_type(user) in manager_types


class CanViewDocumentationArticle(BasePermission):

    def has_object_permission(self, request, view, obj):
        return can_view_article(request.user, obj)


class CanManageDocumentationArticle(BasePermission):

    def has_object_permission(self, request, view, obj):
        return can_manage_article(request.user, obj)










def can_manage_scope(user, scope, scope_key=""):
    """
    Checks whether a user can create or assign
    documentation to a particular scope.
    """

    if not user or not user.is_authenticated:
        return False

    if is_system_root(user):
        return True

    manager_types = getattr(
        settings,
        "DOCUMENTATION_MANAGER_USER_TYPES",
        ["RAD", "ADM"],
    )

    if get_user_type(user) not in manager_types:
        return False

    if scope == "global":
        return False

    if scope == "regional":
        if get_user_type(user) != "RAD":
            return False

        return str(scope_key) in get_managed_county_ids(user)

    if scope == "school":
        if get_user_type(user) == "RAD":
            return False

        return str(scope_key) == get_school_id(user)

    return False


class IsSystemRoot(BasePermission):
    """
    Only SYS can manage global documentation taxonomy.
    """

    def has_permission(self, request, view):
        return is_system_root(request.user)
