from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import MeetingDetail
from .google_sheets import sync_meeting_to_google_sheet

@receiver(post_save, sender=MeetingDetail)
def meeting_post_save(sender, instance, created, **kwargs):
    """
    Automatically triggers sheet synchronization whenever a meeting is created or updated.
    """
    sync_meeting_to_google_sheet(instance)
