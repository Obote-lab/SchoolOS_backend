"""
URL configuration for schoolOS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/accounts/", include("accounts.urls")),
    path("api/v1/schools/", include("schools.urls")),
    path("api/v1/students/", include("students.urls")),
    path("api/v1/staff/", include("staff.urls")),
    path("api/v1/academics/", include("academics.urls")),
    path("api/v1/attendance/", include("attendance.urls")),
    path("api/v1/finance/", include("finance.urls")),
    path("api/v1/welfare/", include("welfare.urls")),
    path("api/v1/activities/", include("activities.urls")),
    path("api/v1/communications/", include("communications.urls")),
    path("api/v1/compliance/", include("compliance.urls")),
    path("api/v1/dormitory/", include("dormitory.urls")),
    path("api/v1/branding/", include("branding.urls")),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/",SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui",),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
