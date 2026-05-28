from rest_framework import viewsets, permissions
from django.contrib.auth.models import User
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import ProjectDetail, MeetingDetail, UserProfile
from .permissions import IsAdminUserRole
from .serializers import (
    UserProfileSerializer, 
    UserProfileWriteSerializer,
    MyTokenObtainPairSerializer,
    ProjectDetailSerializer, 
    MeetingDetailReadSerializer, 
    MeetingDetailWriteSerializer
)

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows UserProfiles to be managed (Admin only) or listed (Authenticated).
    """
    queryset = UserProfile.objects.all().order_by('emailid')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsAdminUserRole()]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return UserProfileSerializer
        return UserProfileWriteSerializer
        
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Prevent self-deletion
        if instance.user == request.user:
            from rest_framework import status
            from rest_framework.response import Response
            return Response(
                {"detail": "You cannot delete your own account."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Delete linked auth_user first, then the profile
        auth_user = instance.user
        response = super().destroy(request, *args, **kwargs)
        if auth_user:
            auth_user.delete()
        return response
class ProjectDetailViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = ProjectDetail.objects.all().order_by('-created_at')
    serializer_class = ProjectDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

class MeetingDetailViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows meetings to be viewed or edited.
    """
    queryset = MeetingDetail.objects.all().order_by('-date', '-time')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return MeetingDetailReadSerializer
        return MeetingDetailWriteSerializer

    def perform_create(self, serializer):
        # Auto assign organizer if not provided, else use the provided one
        if 'organizer' not in serializer.validated_data:
            serializer.save(organizer=self.request.user)
        else:
            serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Serialize with ReadSerializer for nested fields (organizer, attendees, project)
        read_serializer = MeetingDetailReadSerializer(serializer.instance)
        from rest_framework.response import Response
        from rest_framework import status
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Serialize with ReadSerializer for nested fields (organizer, attendees, project)
        read_serializer = MeetingDetailReadSerializer(instance)
        from rest_framework.response import Response
        return Response(read_serializer.data)
