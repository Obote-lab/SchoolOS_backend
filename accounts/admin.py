from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, Role, UserRole, PermissionMatrix


class CustomUserAdmin(BaseUserAdmin):
    """Admin interface for CustomUser model"""
    
    model = CustomUser
    list_display = (
        'login_id', 'email', 'first_name', 'last_name', 
        'user_type', 'school', 'is_active', 'is_verified'
    )
    list_filter = (
        'user_type', 'is_active', 'is_verified', 'school', 
        'gender', 'preferred_language'
    )
    search_fields = (
        'login_id', 'email', 'first_name', 'last_name', 
        'phone', 'national_id', 'permanent_id'
    )
    ordering = ('-date_joined',)
    readonly_fields = ('permanent_id', 'date_joined', 'last_login')
    
    fieldsets = (
        (None, {'fields': ('login_id', 'password', 'permanent_id')}),
        (_('Personal Info'), {
            'fields': (
                'first_name', 'middle_name', 'last_name', 
                'email', 'phone', 'national_id',
                'date_of_birth', 'gender', 'profile_picture'
            )
        }),
        (_('School Information'), {
            'fields': ('school', 'user_type', 'managed_counties')
        }),
        (_('Address'), {
            'fields': ('county', 'sub_county', 'ward', 'address')
        }),
        (_('Preferences'), {
            'fields': ('preferred_language', 'notification_prefs', 'recovery_email')
        }),
        (_('Security'), {
            'fields': (
                'is_active', 'is_verified', 'can_login',
                'failed_login_attempts', 'locked_until',
                'last_verified_at', 'last_locked_at'
            )
        }),
        (_('Permissions'), {
            'fields': (
                'is_staff', 'is_superuser', 'is_system_root',
                'groups', 'user_permissions'
            )
        }),
        (_('Important dates'), {
            'fields': ('date_joined', 'last_login', 'created_at', 'updated_at')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'login_id', 'email', 'first_name', 'last_name',
                'password1', 'password2', 'school', 'user_type'
            ),
        }),
    )
    
    filter_horizontal = ('groups', 'user_permissions')
    
    def get_queryset(self, request):
        """Limit queryset based on user permissions"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        # School admins only see their school users
        if hasattr(request.user, 'school') and request.user.school:
            return qs.filter(school=request.user.school)
        
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        """Handle password hashing on save"""
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)


class RoleAdmin(admin.ModelAdmin):
    """Admin interface for Role model"""
    list_display = ('name', 'role_category', 'permissions_tier', 'access_level')
    list_filter = ('role_category', 'access_level', 'permissions_tier')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ()


class UserRoleAdmin(admin.ModelAdmin):
    """Admin interface for UserRole model"""
    list_display = ('user', 'role', 'school', 'is_primary_role', 'is_active')
    list_filter = ('is_active', 'is_primary_role', 'role', 'school')
    search_fields = ('user__login_id', 'user__first_name', 'user__last_name')
    readonly_fields = ('assigned_date', 'created_at', 'updated_at')
    raw_id_fields = ('user', 'role', 'school', 'assigned_by')


class PermissionMatrixAdmin(admin.ModelAdmin):
    """Admin interface for PermissionMatrix model"""
    list_display = ('role', 'module', 'action', 'resource_scope', 'is_allowed')
    list_filter = ('module', 'action', 'is_allowed', 'resource_scope')
    search_fields = ('role__name', 'module')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('role', 'created_by')


# Register models
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Role, RoleAdmin)
admin.site.register(UserRole, UserRoleAdmin)
admin.site.register(PermissionMatrix, PermissionMatrixAdmin)