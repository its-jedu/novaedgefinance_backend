from django.urls import path
from .views import home
from .management_views import create_superuser_view


urlpatterns = [
    path('', home, name='home'),
    path("create-superuser/", create_superuser_view, name="create_superuser"),
]