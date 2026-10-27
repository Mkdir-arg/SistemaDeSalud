from django.contrib import admin
from django.urls import path
from .issue136_urls_runtime import urlpatterns as rutas_api

urlpatterns = [path("admin/", admin.site.urls), *rutas_api]
