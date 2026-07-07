"""
URL configuration for setup project.

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

from django.contrib import admin
from django.urls import include, path

from apps.core.views import (
    LoginView,
    RefreshView,
    LogoutView,
    logout_all,
    me,
    password_reset_request,
    password_reset_confirm,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/login/", LoginView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", RefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/me/", me, name="me"),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/logout/", LogoutView.as_view(), name="token_blacklist"),
    path("api/v1/auth/logout-all/", logout_all, name="logout_all"),
    path("api/v1/auth/password-reset/request/", password_reset_request, name="password_reset_request"),
    path("api/v1/auth/password-reset/confirm/", password_reset_confirm, name="password_reset_confirm"),
]
