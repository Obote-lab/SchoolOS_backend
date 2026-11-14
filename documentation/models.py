import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class DocumentationCategory(models.Model):
    """
    Groups documentation articles into logical sections.
    """

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180,unique=True,blank=True,)
    description = models.TextField(blank=True)
    icon = models.CharField( max_length=60, blank=True,help_text="Optional icon identifier for the frontend.",)
    parent = models.ForeignKey("self",on_delete=models.SET_NULL,null=True,blank=True,related_name="subcategories",)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Documentation Category"
        verbose_name_plural = "Documentation Categories"
        ordering = ["order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class DocumentationTag(models.Model):
    """
    Keywords used to organize and search articles.
    """
    id = models.UUIDField( primary_key=True, default=uuid.uuid4, editable=False,)
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField( max_length=100,  unique=True,  blank=True,)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class DocumentationArticle(models.Model):
    """
    Main documentation content.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Scope(models.TextChoices):
        GLOBAL = "global", "Global"
        REGIONAL = "regional", "Regional"
        SCHOOL = "school", "School"

    class ContentFormat(models.TextChoices):
        MARKDOWN = "markdown", "Markdown"
        HTML = "html", "HTML"
        TEXT = "text", "Plain Text"

    id = models.UUIDField( primary_key=True, default=uuid.uuid4, editable=False,)
    title = models.CharField(max_length=255)
    slug = models.SlugField( max_length=280, unique=True, blank=True,)
    excerpt = models.CharField( max_length=500, blank=True,)
    content = models.TextField()
    content_format = models.CharField(max_length=20,choices=ContentFormat.choices,default=ContentFormat.MARKDOWN,)
    category = models.ForeignKey( DocumentationCategory,on_delete=models.PROTECT,related_name="articles",)
    tags = models.ManyToManyField(DocumentationTag,blank=True,related_name="articles",)
    status = models.CharField( max_length=20,choices=Status.choices,default=Status.DRAFT, )
    scope = models.CharField(max_length=20,choices=Scope.choices,default=Scope.GLOBAL, )

    # County ID for regional content or school ID
    # for school-specific content.
    scope_key = models.CharField( max_length=100, blank=True, db_index=True,)
    # Example: ["SYS", "RAD", "ADM", "TCH"]
    # An empty list means all authenticated user types.
    audience_roles = models.JSONField(default=list, blank=True)
    featured = models.BooleanField(default=False)
    allow_feedback = models.BooleanField(default=True)
    reading_time = models.PositiveIntegerField( default=1,validators=[MinValueValidator(1)],)
    view_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField( null=True, blank=True,)
    archived_at = models.DateTimeField(null=True,blank=True,)
    author = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name="documentation")
    last_modified_by = models.ForeignKey( settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="documentation_modified",)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-featured", "-published_at", "-created_at"]

        indexes = [
            models.Index(fields=["status", "scope"]),
            models.Index(fields=["category", "status"]),
            models.Index(fields=["scope", "scope_key"]),
            models.Index(fields=["published_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            self.slug = base_slug or str(uuid.uuid4())

            candidate = self.slug
            counter = 1

            while DocumentationArticle.objects.filter(
                slug=candidate
            ).exclude(pk=self.pk).exists():
                counter += 1
                candidate = f"{base_slug}-{counter}"

            self.slug = candidate

        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        if self.status == self.Status.ARCHIVED and not self.archived_at:
            self.archived_at = timezone.now()

        if self.status != self.Status.ARCHIVED:
            self.archived_at = None

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ArticleRevision(models.Model):
    """
    Stores snapshots of article changes.
    """

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    article = models.ForeignKey( DocumentationArticle, on_delete=models.CASCADE, related_name="revisions")
    revision_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    content = models.TextField()
    excerpt = models.CharField(max_length=500, blank=True)
    content_format = models.CharField(max_length=20)
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name="documentation_revisions",)
    change_summary = models.CharField(max_length=255,blank=True, )
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ["-revision_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["article", "revision_number"],
                name="unique_article_revision",
            )
        ]

    def __str__(self):
        return f"{self.article.title} - Revision {self.revision_number}"


class ArticleFeedback(models.Model):
    """
    Records user feedback on documentation articles.
    """

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False, )
    article = models.ForeignKey( DocumentationArticle, on_delete=models.CASCADE, related_name="feedback",)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="documentation_feedback",)
    is_helpful = models.BooleanField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["article", "user"],
                name="unique_article_user_feedback",
            )
        ]

    def __str__(self):
        return f"Feedback: {self.article.title}"


class ArticleView(models.Model):
    """
    Tracks authenticated user readership.
    One record per user per article.
    """

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    article = models.ForeignKey(DocumentationArticle,on_delete=models.CASCADE,related_name="reader_records",)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="documentation_views", )
    first_viewed_at = models.DateTimeField(auto_now_add=True)
    last_viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["article", "user"],
                name="unique_article_user_view",
            )
        ]

    def __str__(self):
        return f"{self.user} viewed {self.article.title}"
