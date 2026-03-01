from django.urls import path
from .views import home
from .management_views import create_default_superuser


urlpatterns = [
    path('', home, name='home'),
    path("create-superuser/", create_default_superuser, name="create_superuser"),
]