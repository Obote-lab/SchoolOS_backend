import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings


class TimeStampedModel(models.Model):
    """
    Abstract base that adds created_at and updated_at.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """
    Abstract base that uses UUID as primary key.
    """
    id = models.UUIDField( primary_key=True,default=uuid.uuid4, editable=False,db_index=True,)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return super().update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=True)


class SoftDeleteModel(models.Model):
    """
    Abstract base for soft deletion.
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True, on_delete=models.SET_NULL,related_name="%(class)s_deleted",)

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # includes deleted

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user:
            self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])


class SchoolScopedModel(models.Model):
    """
    Abstract base for models that belong to a specific school.
    The SchoolContextMiddleware will usually inject the current school.
    """
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        db_index=True,
    )

#     organization = models.ForeignKey(
#     "organization.Organization",
#     on_delete=models.CASCADE,
#     db_index=True,
# )

    class Meta:
        abstract = True


class UserOwnedModel(models.Model):
    """
    Abstract base for models owned/created by a user.
    """
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True,blank=True,related_name="%(class)s_created",)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True, blank=True,related_name="%(class)s_updated",)

    created_from_ip = models.GenericIPAddressField(null=True, blank=True)
    updated_from_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    """
    The standard base model used across the entire platform.
    """
    class Meta:
        abstract = True


class SchoolScopedBaseModel(BaseModel, SchoolScopedModel, UserOwnedModel):
    """
    Most school-related models inherit from this.
    """
    class Meta:
        abstract = True