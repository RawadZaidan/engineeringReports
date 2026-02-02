import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.conf import settings

def create_superuser():
    User = get_user_model()
    
    # Credentials - You can change these if you want
    username = "admin"
    email = "admin@medilab.com"
    password = "adminpassword123"  # Change this after logging in!

    if not User.objects.filter(username=username).exists():
        print(f"Creating superuser '{username}'...")
        try:
            User.objects.create_superuser(username, email, password)
            print(f"✅ Superuser '{username}' created successfully!")
        except Exception as e:
            print(f"❌ Failed to create superuser: {e}")
    else:
        print(f"✅ Superuser '{username}' already exists. Skipping.")

if __name__ == "__main__":
    create_superuser()
