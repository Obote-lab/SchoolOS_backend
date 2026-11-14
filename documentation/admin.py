
# documentation/admin.py

from django.contrib import admin

from .models import (
    DocumentationCategory,
    DocumentationTag,
    DocumentationArticle,
    ArticleRevision,
    ArticleFeedback,
    ArticleView,
)


@admin.register(DocumentationCategory)
class DocumentationCategoryAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "parent",
        "order",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "parent",
    )

    search_fields = (
        "name",
        "description",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    ordering = ("order", "name")


@admin.register(DocumentationTag)
class DocumentationTagAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "slug",
        "created_at",
    )

    search_fields = ("name",)

    prepopulated_fields = {
        "slug": ("name",),
    }


class ArticleRevisionInline(admin.TabularInline):

    model = ArticleRevision

    extra = 0

    can_delete = False

    readonly_fields = (
        "revision_number",
        "title",
        "edited_by",
        "change_summary",
        "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DocumentationArticle)
class DocumentationArticleAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "category",
        "status",
        "scope",
        "featured",
        "view_count",
        "author",
        "published_at",
    )

    list_filter = (
        "status",
        "scope",
        "featured",
        "content_format",
        "category",
    )

    search_fields = (
        "title",
        "excerpt",
        "content",
    )

    filter_horizontal = ("tags",)

    readonly_fields = (
        "view_count",
        "published_at",
        "archived_at",
        "created_at",
        "updated_at",
    )

    inlines = [ArticleRevisionInline]

    fieldsets = (
        (
            "Article Information",
            {
                "fields": (
                    "title",
                    "slug",
                    "excerpt",
                    "content",
                    "content_format",
                    "category",
                    "tags",
                )
            },
        ),
        (
            "Access and Visibility",
            {
                "fields": (
                    "status",
                    "scope",
                    "scope_key",
                    "audience_roles",
                )
            },
        ),
        (
            "Settings",
            {
                "fields": (
                    "featured",
                    "allow_feedback",
                    "reading_time",
                )
            },
        ),
        (
            "Ownership",
            {
                "fields": (
                    "author",
                    "last_modified_by",
                )
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "view_count",
                    "published_at",
                    "archived_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    ordering = ("-created_at",)


@admin.register(ArticleRevision)
class ArticleRevisionAdmin(admin.ModelAdmin):

    list_display = (
        "article",
        "revision_number",
        "edited_by",
        "created_at",
    )

    search_fields = (
        "article__title",
        "change_summary",
    )

    readonly_fields = (
        "article",
        "revision_number",
        "title",
        "content",
        "excerpt",
        "content_format",
        "edited_by",
        "change_summary",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ArticleFeedback)
class ArticleFeedbackAdmin(admin.ModelAdmin):

    list_display = (
        "article",
        "user",
        "is_helpful",
        "created_at",
    )

    list_filter = (
        "is_helpful",
        "created_at",
    )

    search_fields = (
        "article__title",
        "user__login_id",
        "comment",
    )

    readonly_fields = (
        "article",
        "user",
        "is_helpful",
        "comment",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(ArticleView)
class ArticleViewAdmin(admin.ModelAdmin):

    list_display = (
        "article",
        "user",
        "first_viewed_at",
        "last_viewed_at",
    )

    list_filter = (
        "first_viewed_at",
    )

    search_fields = (
        "article__title",
        "user__login_id",
    )

    readonly_fields = (
        "article",
        "user",
        "first_viewed_at",
        "last_viewed_at",
    )

    def has_add_permission(self, request):
        return False
