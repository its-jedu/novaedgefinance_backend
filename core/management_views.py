from django.http import HttpResponse
from django.conf import settings
from authentication.models import User

def create_superuser_view(request):
    # Only allow in DEBUG mode for safety
    if not settings.DEBUG:
        return HttpResponse("Not allowed", status=403)

    # Superuser credentials - change these
    email = "admin@novaedgefinance.com"
    password = "Sm!L3Y2026"
    first_name = "Admin"
    last_name = "User"
    country = "USA"

    # Check if superuser already exists
    if User.objects.filter(email=email).exists():
        return HttpResponse("Superuser already exists")

    # Create superuser using your custom manager
    User.objects.create_superuser(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        country=country
    )

    return HttpResponse(f"Superuser '{email}' created successfully!")