import json
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from django.db import transaction
from mom_api.models import Reminder, PushSubscription, MeetingDetail

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    # Fallback to prevent import error if package is installing
    webpush = None
    WebPushException = Exception


class Command(BaseCommand):
    help = "Dispatches due calendar reminders and upcoming meeting notifications via Web Push"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting reminder dispatch check..."))

        # Get the current time in local timezone
        now = timezone.localtime(timezone.now())
        current_date = now.date()
        current_time = now.time()
        now_local = now.replace(tzinfo=None)

        # ----------------------------------------------------
        # 1. Process Calendar Reminders
        # ----------------------------------------------------
        with transaction.atomic():
            # Query unsent reminders whose date <= current_date, and if date == current_date, time <= current_time
            due_reminders = Reminder.objects.select_for_update().filter(
                is_sent=False
            ).filter(
                Q(date__lt=current_date) | Q(date=current_date, time__lte=current_time)
            )

            # Evaluate count within transaction
            count = list(due_reminders)
            if count:
                self.stdout.write(self.style.SUCCESS(f"Found {len(count)} due reminder(s) to process."))

                for reminder in count:
                    user = reminder.user
                    title = reminder.title
                    desc = reminder.description or ""
                    time_str = reminder.time.strftime("%I:%M %p")

                    # Send Web Push Notification
                    push_subscriptions = PushSubscription.objects.filter(user=user)
                    push_count = push_subscriptions.count()
                    
                    if push_count > 0:
                        if webpush is None:
                            self.stdout.write(self.style.ERROR("pywebpush package is not installed/imported. Skipping Web Push."))
                        elif not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
                            self.stdout.write(self.style.ERROR("VAPID keys not configured in settings. Skipping Web Push."))
                        else:
                            payload = {
                                "title": f"MOM Reminder: {title}",
                                "body": desc or f"Scheduled for today at {time_str}",
                                "url": "/dashboard/calendar"
                            }
                            
                            for sub in push_subscriptions:
                                sub_info = {
                                    "endpoint": sub.endpoint,
                                    "keys": {
                                        "p256dh": sub.p256dh,
                                        "auth": sub.auth
                                    }
                                }
                                try:
                                    webpush(
                                        subscription_info=sub_info,
                                        data=json.dumps(payload),
                                        vapid_private_key=settings.VAPID_PRIVATE_KEY,
                                        vapid_claims=settings.VAPID_CLAIMS
                                    )
                                    self.stdout.write(self.style.SUCCESS(f"Sent push notification to subscription {sub.id} of {user.username}"))
                                except WebPushException as ex:
                                    if ex.response is not None and ex.response.status_code in [404, 410]:
                                        self.stdout.write(self.style.WARNING(f"Cleaning up expired/invalid subscription {sub.id}"))
                                        sub.delete()
                                    else:
                                        self.stdout.write(self.style.ERROR(f"Failed to send push: {ex}"))
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f"Unexpected error sending push: {e}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"User {user.username} has no active web push subscriptions."))

                    # Mark reminder as sent
                    reminder.is_sent = True
                    reminder.save()
                    self.stdout.write(self.style.SUCCESS(f"Reminder {reminder.id} marked as sent."))
            else:
                self.stdout.write(self.style.SUCCESS("No pending due reminders found."))

        # ----------------------------------------------------
        # 2. Process Upcoming Meetings Push Notifications
        # ----------------------------------------------------
        self.stdout.write(self.style.SUCCESS("Starting upcoming meetings dispatch check..."))

        # We query meetings whose start time is in the future
        # and at least one notification has not been sent yet.
        upcoming_meetings = MeetingDetail.objects.filter(
            Q(notification_24h_sent=False) | Q(notification_1h_sent=False)
        ).filter(
            Q(date__gt=current_date) | Q(date=current_date, time__gt=current_time)
        )

        for meeting in upcoming_meetings:
            meeting_local_dt = datetime.combine(meeting.date, meeting.time)
            time_difference = meeting_local_dt - now_local

            # Calculate triggers
            send_24h = False
            send_1h = False

            if time_difference > timedelta(0):  # In the future
                if time_difference <= timedelta(hours=24) and not meeting.notification_24h_sent:
                    send_24h = True
                if time_difference <= timedelta(hours=1) and not meeting.notification_1h_sent:
                    send_1h = True

            if not send_24h and not send_1h:
                continue

            # Gather all recipients
            recipients = set()
            if meeting.organizer:
                recipients.add(meeting.organizer)
            if meeting.attendees:
                for attendee in meeting.attendees.all():
                    recipients.add(attendee)

            formatted_time = meeting.time.strftime("%I:%M %p")

            # Determine title, body, type
            if send_1h:
                title = f"MOM: Upcoming Meeting"
                body = f"'{meeting.title}' starts in 1 hour (at {formatted_time})"
                self.stdout.write(self.style.SUCCESS(f"Triggering 1h notification for meeting {meeting.id} ('{meeting.title}')"))
            else:
                title = f"MOM: Upcoming Meeting"
                body = f"'{meeting.title}' starts in 24 hours (on {meeting.date} at {formatted_time})"
                self.stdout.write(self.style.SUCCESS(f"Triggering 24h notification for meeting {meeting.id} ('{meeting.title}')"))

            payload = {
                "title": title,
                "body": body,
                "url": f"/dashboard/meetings/{meeting.id}"
            }

            for user in recipients:
                push_subscriptions = PushSubscription.objects.filter(user=user)
                if push_subscriptions.count() > 0:
                    if webpush is not None and settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY:
                        for sub in push_subscriptions:
                            sub_info = {
                                "endpoint": sub.endpoint,
                                "keys": {
                                    "p256dh": sub.p256dh,
                                    "auth": sub.auth
                                }
                            }
                            try:
                                webpush(
                                    subscription_info=sub_info,
                                    data=json.dumps(payload),
                                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                                    vapid_claims=settings.VAPID_CLAIMS
                                )
                                self.stdout.write(self.style.SUCCESS(f"Sent push notification to subscription {sub.id} of {user.username} for meeting {meeting.id}"))
                            except WebPushException as ex:
                                if ex.response is not None and ex.response.status_code in [404, 410]:
                                    self.stdout.write(self.style.WARNING(f"Cleaning up expired/invalid subscription {sub.id}"))
                                    sub.delete()
                                else:
                                    self.stdout.write(self.style.ERROR(f"Failed to send push: {ex}"))
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f"Unexpected error sending push: {e}"))
                else:
                    self.stdout.write(self.style.WARNING(f"User {user.username} has no active web push subscriptions."))

            # Update notification sent statuses in a transactional update
            with transaction.atomic():
                try:
                    m_to_update = MeetingDetail.objects.select_for_update().get(id=meeting.id)
                    if send_24h:
                        m_to_update.notification_24h_sent = True
                    if send_1h:
                        m_to_update.notification_1h_sent = True
                    m_to_update.save()
                    self.stdout.write(self.style.SUCCESS(f"Meeting {meeting.id} notification flags updated: 24h={m_to_update.notification_24h_sent}, 1h={m_to_update.notification_1h_sent}"))
                except MeetingDetail.DoesNotExist:
                    pass

        self.stdout.write(self.style.SUCCESS("Reminder and upcoming meeting check completed."))
