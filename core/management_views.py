from django.conf import settings
from authentication.models import User

def create_default_superuser():
    if not settings.DEBUG:
        return

    email = "admin@novaedgefinance.com"

    if User.objects.filter(email=email).exists():
        return

    User.objects.create_superuser(
        email=email,
        password="Sm!L3Y2026",
        first_name="Admin",
        last_name="User",
        country="USA"
    )

    print("Default superuser created")