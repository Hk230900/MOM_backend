from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from mom_api.models import UserProfile

class Command(BaseCommand):
    help = 'Seed superuser (auth_user only) and Harshada Kale Admin profile'

    def handle(self, *args, **options):
        # 1. Seed standard superuser (admin) - ONLY in auth_user
        superuser_username = 'admin'
        superuser_email = 'admin@example.com'
        superuser_password = 'Mom@0123$Mom'

        user, created = User.objects.get_or_create(
            username=superuser_username,
            defaults={'email': superuser_email, 'is_superuser': True, 'is_staff': True}
        )

        user.set_password(superuser_password)
        user.is_superuser = True
        user.is_staff = True
        user.save()
        self.stdout.write(self.style.SUCCESS("Superuser 'admin' created/updated inside auth_user table."))

        # Delete any UserProfile for 'admin' if it exists to keep it isolated
        UserProfile.objects.filter(user=user).delete()
        UserProfile.objects.filter(emailid='admin@example.com').delete()
        self.stdout.write(self.style.WARNING("Isolated 'admin' superuser from UserProfile table."))

        # 2. Seed Admin user profile for Harshada Kale
        h_first_name = 'Harshada'
        h_last_name = 'Kale'
        h_emailid = 'harshadabk2309@gmail.com'
        h_password = 'HarshadaK@23*/'
        h_role = 'Admin'
        h_active = 'Active'

        # Check if profile already exists
        profile = UserProfile.objects.filter(emailid=h_emailid).first()
        if not profile:
            profile = UserProfile.objects.create(
                first_name=h_first_name,
                last_name=h_last_name,
                emailid=h_emailid,
                password=h_password,
                active=h_active,
                role=h_role
            )
            
            # The UserProfile.save() signal is not used, creation links it via serializers, 
            # but here in management command we will manually sync/link to auth_user:
            h_user, h_created = User.objects.get_or_create(
                username=h_emailid,
                defaults={'email': h_emailid, 'first_name': h_first_name, 'last_name': h_last_name, 'is_active': True}
            )
            h_user.set_password(h_password)
            h_user.first_name = h_first_name
            h_user.last_name = h_last_name
            h_user.is_active = True
            h_user.save()
            
            profile.user = h_user
            profile.save()
            self.stdout.write(self.style.SUCCESS(f"Successfully seeded UserProfile and auth_user for {h_first_name} {h_last_name}."))
        else:
            profile.first_name = h_first_name
            profile.last_name = h_last_name
            profile.active = h_active
            profile.role = h_role
            profile.password = h_password # This will run hashing inside profile.save()
            profile.save()

            h_user = profile.user
            if not h_user:
                h_user, _ = User.objects.get_or_create(
                    username=h_emailid,
                    defaults={'email': h_emailid, 'first_name': h_first_name, 'last_name': h_last_name, 'is_active': True}
                )
            h_user.username = h_emailid
            h_user.email = h_emailid
            h_user.first_name = h_first_name
            h_user.last_name = h_last_name
            h_user.is_active = True
            h_user.password = profile.password # Sync hashed password
            h_user.save()
            
            profile.user = h_user
            profile.save()
            self.stdout.write(self.style.SUCCESS(f"Updated UserProfile and auth_user records for {h_first_name} {h_last_name}."))
