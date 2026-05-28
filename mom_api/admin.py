# Register your models here.
from django.contrib import admin
from .models import ProjectDetail, MeetingDetail, UserProfile

admin.site.register(ProjectDetail)
admin.site.register(MeetingDetail)
admin.site.register(UserProfile)
