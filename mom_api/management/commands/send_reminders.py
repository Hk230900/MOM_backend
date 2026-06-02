import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.db import transaction
from mom_api.models import Reminder, PushSubscription

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    # Fallback to prevent import error if package is installing
    webpush = None
    WebPushException = Exception


class Command(BaseCommand):
    help = "Dispatches due calendar reminders via Email and Web Push Notifications"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting reminder dispatch check..."))

        # Get the current time in local timezone
        now = timezone.localtime(timezone.now())
        current_date = now.date()
        current_time = now.time()

        with transaction.atomic():
            # Query unsent reminders whose date <= current_date, and if date == current_date, time <= current_time
            due_reminders = Reminder.objects.select_for_update().filter(
                is_sent=False
            ).filter(
                Q(date__lt=current_date) | Q(date=current_date, time__lte=current_time)
            )

            # Evaluate count within transaction
            count = list(due_reminders)
            if not count:
                self.stdout.write(self.style.SUCCESS("No pending due reminders found."))
                return

            self.stdout.write(self.style.SUCCESS(f"Found {len(count)} due reminder(s) to process."))

            for reminder in count:
                user = reminder.user
                title = reminder.title
                desc = reminder.description or ""
                date_str = reminder.date.strftime("%d-%m-%Y")
                time_str = reminder.time.strftime("%I:%M %p")

                # 1. Send Email Notification
                email_sent = False
                user_email = getattr(user, 'email', None)
                if hasattr(user, 'profile') and user.profile.emailid:
                    user_email = user.profile.emailid

                if user_email:
                    subject = f"MOM Reminder: {title}"
                    message = (
                        f"Hello {user.first_name or user.username},\n\n"
                        f"This is a reminder for: \"{title}\"\n"
                        f"Details: {desc}\n"
                        f"Scheduled for: {date_str} at {time_str}\n\n"
                        f"Best regards,\nMOM Manager Admin"
                    )
                    try:
                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [user_email],
                            fail_silently=False,
                        )
                        email_sent = True
                        self.stdout.write(self.style.SUCCESS(f"Sent email to {user_email} for reminder: {title}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Failed to send email to {user_email}: {e}"))
                else:
                    self.stdout.write(self.style.WARNING(f"User {user.username} has no email address. Skipping email."))

                # 2. Send Web Push Notification
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
                                # 404 or 410 means the subscription has expired or unsubscribed, so clean it up
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

        self.stdout.write(self.style.SUCCESS("Reminder dispatch completed."))
