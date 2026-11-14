from rest_framework import serializers
from ..models import (
    DocumentationCategory,
    DocumentationTag,
    DocumentationArticle,
    ArticleRevision,
    ArticleFeedback,
)


class DocumentationCategorySerializer(serializers.ModelSerializer):

    article_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentationCategory
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "parent",
            "order",
            "is_active",
            "article_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "slug",
            "created_at",
            "updated_at",
        ]

    def get_article_count(self, obj):
        return obj.articles.filter(
            status=DocumentationArticle.Status.PUBLISHED
        ).count()


class DocumentationTagSerializer(serializers.ModelSerializer):

    class Meta:
        model = DocumentationTag
        fields = [
            "id",
            "name",
            "slug",
            "created_at",
        ]

        read_only_fields = ["id", "slug", "created_at"]


class DocumentationRevisionSerializer(serializers.ModelSerializer):

    edited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ArticleRevision
        fields = [
            "id",
            "revision_number",
            "title",
            "content",
            "excerpt",
            "content_format",
            "edited_by_name",
            "change_summary",
            "created_at",
        ]

        read_only_fields = fields

    def get_edited_by_name(self, obj):
        if not obj.edited_by:
            return None

        return obj.edited_by.get_full_name() or obj.edited_by.login_id


class DocumentationArticleListSerializer(serializers.ModelSerializer):

    category = DocumentationCategorySerializer(read_only=True)

    tags = DocumentationTagSerializer(many=True, read_only=True)

    author_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentationArticle
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "category",
            "tags",
            "status",
            "scope",
            "featured",
            "reading_time",
            "view_count",
            "published_at",
            "author_name",
            "created_at",
            "updated_at",
        ]

    def get_author_name(self, obj):
        if not obj.author:
            return None

        return obj.author.get_full_name() or obj.author.login_id


class DocumentationArticleDetailSerializer(
    DocumentationArticleListSerializer
):

    content = serializers.CharField()

    content_format = serializers.CharField()

    audience_roles = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
    )

    allow_feedback = serializers.BooleanField()

    class Meta(DocumentationArticleListSerializer.Meta):
        fields = DocumentationArticleListSerializer.Meta.fields + [
            "content",
            "content_format",
            "audience_roles",
            "allow_feedback",
            "scope_key",
        ]


class DocumentationArticleWriteSerializer(serializers.ModelSerializer):

    category = serializers.PrimaryKeyRelatedField(
        queryset=DocumentationCategory.objects.all()
    )

    tags = serializers.PrimaryKeyRelatedField(
        queryset=DocumentationTag.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = DocumentationArticle

        fields = [
            "title",
            "excerpt",
            "content",
            "content_format",
            "category",
            "tags",
            "scope",
            "scope_key",
            "audience_roles",
            "featured",
            "allow_feedback",
            "reading_time",
        ]

    def validate_category(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "You cannot use an inactive category."
            )

        return value

    def validate_audience_roles(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate audience roles are not allowed."
            )

        if any(not role.strip() for role in value):
            raise serializers.ValidationError(
                "Audience roles cannot contain empty values."
            )

        return value

    def validate(self, attrs):
        scope = attrs.get(
            "scope",
            getattr(self.instance, "scope", "global"),
        )

        scope_key = attrs.get(
            "scope_key",
            getattr(self.instance, "scope_key", ""),
        )

        if scope in ["regional", "school"] and not scope_key:
            raise serializers.ValidationError({
                "scope_key": (
                    "A county or school identifier is required "
                    "for regional or school documentation."
                )
            })

        if scope == "global":
            attrs["scope_key"] = ""

        return attrs


class ArticleFeedbackSerializer(serializers.ModelSerializer):

    class Meta:
        model = ArticleFeedback

        fields = [
            "id",
            "is_helpful",
            "comment",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

        extra_kwargs = {
            "comment": {
                "required": False,
                "allow_blank": True,
            }
        }
