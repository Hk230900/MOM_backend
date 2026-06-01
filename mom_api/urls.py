from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, 
    ProjectDetailViewSet, 
    MeetingDetailViewSet,
    ReminderViewSet,
    PushSubscriptionViewSet,
    vapid_public_key
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'projects', ProjectDetailViewSet, basename='project')
router.register(r'meetings', MeetingDetailViewSet, basename='meeting')
router.register(r'reminders', ReminderViewSet, basename='reminder')
router.register(r'webpush/subscribe', PushSubscriptionViewSet, basename='webpush-subscribe')

urlpatterns = [
    path('', include(router.urls)),
    path('webpush/vapid-public-key/', vapid_public_key, name='vapid-public-key'),
]

