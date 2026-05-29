from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, ProjectDetailViewSet, MeetingDetailViewSet, ClientViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'projects', ProjectDetailViewSet, basename='project')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'meetings', MeetingDetailViewSet, basename='meeting')

urlpatterns = [
    path('', include(router.urls)),
]
