from rest_framework.routers import DefaultRouter
from documentation.api.viewsets import DocumentationCategoryViewSet

from .api.viewsets import (
    DocumentationCategoryViewSet,
    DocumentationTagViewSet,
    DocumentationArticleViewSet,
)


router = DefaultRouter()
router.register(r"categories",DocumentationCategoryViewSet,basename="documentation-category",)
router.register(r"tags", DocumentationTagViewSet,basename="documentation-tag",)
router.register(r"articles", DocumentationArticleViewSet,basename="documentation-article",)

urlpatterns = router.urls
