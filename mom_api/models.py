from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password

class ProjectDetail(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    organization = models.CharField(max_length=50, default='iSyra')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Client(models.Model):
    name = models.CharField(max_length=255, unique=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class MeetingDetail(models.Model):
    MEETING_TYPES = (
        ('Internal', 'Internal'),
        ('External', 'External'),
    )
    meeting_type = models.CharField(max_length=10, choices=MEETING_TYPES, default='Internal')
    project = models.ForeignKey(ProjectDetail, on_delete=models.CASCADE, related_name='meetings', null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='meetings', null=True, blank=True)
    title = models.CharField(max_length=255)
    date = models.DateField()
    time = models.TimeField()
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_meetings')
    attendees = models.ManyToManyField(User, related_name='attended_meetings', blank=True)
    agenda = models.TextField(blank=True, null=True)
    minutes = models.TextField(blank=True, null=True)
    action_items = models.JSONField(default=list, blank=True)
    follow_up_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='follow_ups')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        context_name = self.project.name if self.project else (self.client.name if self.client else "No Context")
        return f"{self.title} - {context_name} ({self.date})"

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('Admin', 'Admin'),
        ('Standard', 'Standard'),
    )
    ACTIVE_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    emailid = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    active = models.CharField(max_length=10, choices=ACTIVE_CHOICES, default='Active')
    last_login_date = models.CharField(max_length=10, null=True, blank=True)
    last_login_time = models.CharField(max_length=8, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Standard')
    organization = models.CharField(max_length=50, default='iSyra')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.password:  # only hash if password is provided
            if not self.password.startswith('pbkdf2_'):
                self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.emailid} ({self.role})"


class Reminder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    time = models.TimeField()
    is_sent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Reminder: {self.title} for {self.user.username} on {self.date} at {self.time}"


class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PushSubscription for {self.user.username}"

