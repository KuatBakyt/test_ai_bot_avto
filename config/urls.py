from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from studio.views import JobViewSet, configuration, health, public_photo
router = DefaultRouter()
router.register('jobs', JobViewSet, basename='job')
urlpatterns = [path('admin/', admin.site.urls), path('health/', health),
    path('api/v1/auth/login/', TokenObtainPairView.as_view()),
    path('api/v1/auth/refresh/', TokenRefreshView.as_view()), path('api/v1/config/', configuration),
    path('api/v1/', include(router.urls)), path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema')),
    path('public/photos/<uuid:token>/', public_photo)]
