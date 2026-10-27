from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.accounts.auth_views import LoginInstitucionalView, LogoutInstitucionalView
from .issue136_urls import urlpatterns as rutas_api

urlpatterns = [
    path("api/auth/token/", LoginInstitucionalView.as_view()),
    path("api/auth/token/refresh/", TokenRefreshView.as_view()),
    path("api/auth/logout/", LogoutInstitucionalView.as_view()),
    *rutas_api,
]
