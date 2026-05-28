from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import ProjectDetail, MeetingDetail, UserProfile

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.profile.role if hasattr(user, 'profile') else ('Admin' if user.is_superuser else 'Standard')
        token['username'] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        
        if user.is_superuser:
            data['role'] = 'Admin'
            data['username'] = user.username
            data['email'] = user.email or 'admin@example.com'
            data['fullname'] = 'System Administrator'
            return data
            
        # For normal users, fetch their profile and update last login dates
        profile = UserProfile.objects.filter(user=user).first()
        if profile:
            from django.utils import timezone
            now = timezone.now()
            profile.last_login_date = now.strftime("%d-%m-%Y")
            profile.last_login_time = now.strftime("%H:%M:%S")
            profile.save(update_fields=['last_login_date', 'last_login_time'])
            
            data['role'] = profile.role
            data['username'] = user.username
            data['email'] = profile.emailid
            data['fullname'] = f"{profile.first_name} {profile.last_name}".strip()
        else:
            data['role'] = 'Standard'
            data['username'] = user.username
            data['email'] = user.email
            data['fullname'] = user.username
            
        return data

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'id', 'first_name', 'last_name', 'emailid', 
            'active', 'last_login_date', 'last_login_time', 'role'
        ]

class UserProfileWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = UserProfile
        fields = ['id', 'first_name', 'last_name', 'emailid', 'password', 'active', 'role']

    def create(self, validated_data):
        password = validated_data.get('password', None)
        # Create local UserProfile first (this runs local save which hashes password)
        profile = UserProfile.objects.create(**validated_data)
        
        # Sync and create record in auth_user table
        auth_user = User.objects.create(
            username=profile.emailid,
            email=profile.emailid,
            first_name=profile.first_name,
            last_name=profile.last_name,
            is_active=(profile.active == 'Active'),
            password=profile.password # Use already hashed password from profile
        )
        
        # Link relations
        profile.user = auth_user
        profile.save(update_fields=['user'])
        return profile

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        
        if password:
            instance.password = password
            
        instance = super().update(instance, validated_data)
        
        # Sync update to linked auth User
        if instance.user:
            auth_user = instance.user
            auth_user.username = instance.emailid
            auth_user.email = instance.emailid
            auth_user.first_name = instance.first_name
            auth_user.last_name = instance.last_name
            auth_user.is_active = (instance.active == 'Active')
            if password:
                auth_user.password = instance.password # Already hashed
            auth_user.save()
        else:
            auth_user = User.objects.create(
                username=instance.emailid,
                email=instance.emailid,
                first_name=instance.first_name,
                last_name=instance.last_name,
                is_active=(instance.active == 'Active'),
                password=instance.password
            )
            instance.user = auth_user
            instance.save(update_fields=['user'])
            
        return instance

class ProjectDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectDetail
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']

# Re-use standard User mappings for meeting details views
class MeetingUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class MeetingDetailReadSerializer(serializers.ModelSerializer):
    project = ProjectDetailSerializer(read_only=True)
    organizer = MeetingUserSerializer(read_only=True)
    attendees = MeetingUserSerializer(many=True, read_only=True)

    class Meta:
        model = MeetingDetail
        fields = [
            'id', 'project', 'title', 'date', 'time', 
            'organizer', 'attendees', 'agenda', 'minutes', 
            'action_items', 'created_at', 'updated_at'
        ]

class MeetingDetailWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingDetail
        fields = [
            'id', 'project', 'title', 'date', 'time', 
            'organizer', 'attendees', 'agenda', 'minutes', 
            'action_items'
        ]

    def validate_action_items(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Action items must be a list of objects.")
        return value
