from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from django.conf import settings
from .permissions import can_manage_scope
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .permissions import IsSystemRoot
from ..models import (
    DocumentationCategory,
    DocumentationTag,
    DocumentationArticle,
    ArticleRevision,
    ArticleFeedback,
    ArticleView,
)

from .serializers import (
    DocumentationCategorySerializer,
    DocumentationTagSerializer,
    DocumentationArticleListSerializer,
    DocumentationArticleDetailSerializer,
    DocumentationArticleWriteSerializer,
    DocumentationRevisionSerializer,
    ArticleFeedbackSerializer,
)

from .permissions import (
    CanManageDocumentation,
    can_view_article,
    can_manage_article,
)


class DocumentationCategoryViewSet(viewsets.ModelViewSet):

    serializer_class = DocumentationCategorySerializer
    permission_classes = [IsAuthenticated]

    queryset = DocumentationCategory.objects.all()

    def get_queryset(self):
        queryset = DocumentationCategory.objects.all()

        if self.request.user.user_type != "SYS":
            queryset = queryset.filter(is_active=True)

            queryset = queryset.filter(
                articles__status=DocumentationArticle.Status.PUBLISHED
            ).distinct()

        return queryset

    def get_permissions(self):
        if self.action in ["create","update","partial_update","destroy",]:
            return [IsAuthenticated(), IsSystemRoot()]

        return super().get_permissions()

class DocumentationTagViewSet(viewsets.ModelViewSet):

    serializer_class = DocumentationTagSerializer
    permission_classes = [IsAuthenticated]

    queryset = DocumentationTag.objects.all()

    def get_permissions(self):
        if self.action in ["create","update","partial_update","destroy",]:
            return [IsAuthenticated(), IsSystemRoot()]

        return super().get_permissions()


class DocumentationArticleViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = [
        "title",
        "excerpt",
        "content",
        "category__name",
        "tags__name",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "published_at",
        "view_count",
        "title",
    ]

    ordering = ["-featured", "-published_at"]



    def get_queryset(self):

        user = self.request.user

        queryset = DocumentationArticle.objects.select_related("category","author","last_modified_by",).prefetch_related("tags")

        if user.user_type == "SYS":
            return queryset

        visible = Q(
            status=DocumentationArticle.Status.PUBLISHED
        ) & (
            Q(audience_roles=[]) |
            Q(audience_roles__contains=[user.user_type])
        )

        global_articles = Q(scope="global")

        if user.user_type == "RAD":
            county_ids = [
                str(value)
                for value in user.managed_counties.values_list(
                    "pk",
                    flat=True,
                )
            ]

            regional_articles = Q(
                scope="regional",
                scope_key__in=county_ids,
            )

            managed_articles = regional_articles

        else:
            regional_articles = Q(pk__in=[])

            school_id = str(user.school_id) if user.school_id else ""

            school_articles = Q(
                scope="school",
                scope_key=school_id,
            )

            managed_articles = school_articles

        if user.user_type == "RAD":
            school_articles = Q(pk__in=[])

        readable_articles = visible & (
            global_articles |
            regional_articles |
            school_articles
        )

        return queryset.filter(
            readable_articles | managed_articles
        ).distinct()



    def get_serializer_class(self):

        if self.action == "list":
            return DocumentationArticleListSerializer

        if self.action in ["create", "update", "partial_update"]:
            return DocumentationArticleWriteSerializer

        if self.action == "retrieve":
            return DocumentationArticleDetailSerializer

        return DocumentationArticleDetailSerializer

    def get_permissions(self):

        if self.action == "create":
            return [
                IsAuthenticated(),
                CanManageDocumentation(),
            ]

        if self.action in [
            "update",
            "partial_update",
            "destroy",
            "publish",
            "archive",
            "revisions",
        ]:
            return [IsAuthenticated()]

        return [IsAuthenticated()]


    def perform_create(self, serializer):

        scope = serializer.validated_data.get("scope", "global")
        scope_key = serializer.validated_data.get("scope_key", "")

        if not can_manage_scope(self.request.user,scope,scope_key,):
            raise PermissionDenied("You cannot create documentation in this scope.")

        serializer.save(author=self.request.user,last_modified_by=self.request.user,)

    def perform_update(self, serializer):

        article = self.get_object()

        new_scope = serializer.validated_data.get("scope",article.scope,)
        new_scope_key = serializer.validated_data.get( "scope_key",article.scope_key,)
        if not can_manage_scope(self.request.user,new_scope,new_scope_key,):
            raise PermissionDenied("You cannot move this article to that documentation scope.")

        if not can_manage_article(self.request.user, article):
            raise PermissionDenied("You cannot modify this documentation article.")
        



        with transaction.atomic():

            revision_number = (ArticleRevision.objects.filter(article=article).count() + 1)

            ArticleRevision.objects.create(
                article=article,
                revision_number=revision_number,
                title=article.title,
                content=article.content,
                excerpt=article.excerpt,
                content_format=article.content_format,
                edited_by=self.request.user,
            )

            serializer.save(last_modified_by=self.request.user,)

    def perform_destroy(self, instance):

        if not can_manage_article(self.request.user, instance):
            raise PermissionDenied("You cannot delete this article.")

        if instance.status == DocumentationArticle.Status.PUBLISHED:
            raise PermissionDenied("Archive published articles instead of deleting them.")

        instance.delete()

    def retrieve(self, request, *args, **kwargs):

        instance = self.get_object()

        if not can_view_article(request.user, instance):
            if not can_manage_article(request.user, instance):
                raise PermissionDenied("You cannot access this documentation article.")

        # Track readership once per authenticated user.
        with transaction.atomic():

            _, created = ArticleView.objects.get_or_create(article=instance,user=request.user,)

            if created:
                DocumentationArticle.objects.filter(pk=instance.pk).update(
                    view_count=F("view_count") + 1)

                instance.refresh_from_db(fields=["view_count"])

            else:
                ArticleView.objects.filter(article=instance,user=request.user,).update(
                    last_viewed_at=timezone.now()
                )

        serializer = self.get_serializer(instance)

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):

        article = self.get_object()

        if not can_manage_article(request.user, article):
            raise PermissionDenied(
                "You cannot publish this article."
            )

        if not article.title.strip() or not article.content.strip():
            return Response(
                {"detail": "Title and content are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not article.category.is_active:
            return Response(
                {"detail": "The article category is inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article.status = DocumentationArticle.Status.PUBLISHED
        article.published_at = timezone.now()
        article.archived_at = None
        article.last_modified_by = request.user

        article.save()

        return Response({
            "detail": "Article published successfully.",
            "status": article.status,
            "published_at": article.published_at,
        })

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):

        article = self.get_object()

        if not can_manage_article(request.user, article):
            raise PermissionDenied(
                "You cannot archive this article."
            )

        article.status = DocumentationArticle.Status.ARCHIVED
        article.archived_at = timezone.now()
        article.last_modified_by = request.user

        article.save()

        return Response({
            "detail": "Article archived successfully.",
            "status": article.status,
        })

    @action(detail=True, methods=["get"])
    def revisions(self, request, pk=None):

        article = self.get_object()

        if not can_manage_article(request.user, article):
            raise PermissionDenied(
                "You cannot view revision history."
            )

        revisions = article.revisions.select_related(
            "edited_by"
        )

        serializer = DocumentationRevisionSerializer(
            revisions,
            many=True,
        )

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def feedback(self, request, pk=None):

        article = self.get_object()

        if not can_view_article(request.user, article):
            raise PermissionDenied(
                "You cannot submit feedback for this article."
            )

        if not article.allow_feedback:
            return Response(
                {"detail": "Feedback is disabled for this article."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ArticleFeedbackSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        feedback, created = ArticleFeedback.objects.update_or_create(
            article=article,
            user=request.user,
            defaults=serializer.validated_data,
        )

        return Response(
            ArticleFeedbackSerializer(feedback).data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )

    @action(detail=False, methods=["get"])
    def featured(self, request):

        articles = self.get_queryset().filter(
            status=DocumentationArticle.Status.PUBLISHED,
            featured=True,
        )

        serializer = DocumentationArticleListSerializer(
            articles,
            many=True,
        )

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def popular(self, request):

        articles = self.get_queryset().filter(
            status=DocumentationArticle.Status.PUBLISHED,
        ).order_by("-view_count", "-published_at")[:10]

        serializer = DocumentationArticleListSerializer(
            articles,
            many=True,
        )

        return Response(serializer.data)
