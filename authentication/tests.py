from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import User
import json

class AuthenticationTests(APITestCase):
    
    def setUp(self):
        self.user_data = {
            'email': 'test@novaedge.com',
            'phone_number': '+1234567890',
            'first_name': 'John',
            'last_name': 'Doe',
            'country': 'USA',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!'
        }
    
    def test_user_registration(self):
        url = reverse('register')
        response = self.client.post(url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().email, 'test@novaedge.com')
    
    def test_duplicate_email_registration(self):
        # Create first user
        User.objects.create_user(**{
            'email': 'test@novaedge.com',
            'phone_number': '+1234567890',
            'first_name': 'John',
            'last_name': 'Doe',
            'country': 'USA',
            'password': 'StrongPass123!'
        })
        
        # Try to create duplicate
        url = reverse('register')
        response = self.client.post(url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_with_unverified_user(self):
        # Create unverified user
        user = User.objects.create_user(**{
            'email': 'test@novaedge.com',
            'phone_number': '+1234567890',
            'first_name': 'John',
            'last_name': 'Doe',
            'country': 'USA',
            'password': 'StrongPass123!'
        })
        
        url = reverse('login')
        data = {
            'email': 'test@novaedge.com',
            'password': 'StrongPass123!'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_admin_permissions(self):
        # Create admin user
        admin_user = User.objects.create_superuser(
            email='admin@novaedge.com',
            phone_number='+1987654321',
            password='AdminPass123!'
        )
        
        # Create regular user
        regular_user = User.objects.create_user(
            email='user@novaedge.com',
            phone_number='+1122334455',
            first_name='Jane',
            last_name='Doe',
            country='UK',
            password='UserPass123!'
        )
        
        # Test admin access
        self.client.force_authenticate(user=admin_user)
        url = reverse('admin-users-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test regular user access (should be denied)
        self.client.force_authenticate(user=regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_brute_force_protection(self):
        user = User.objects.create_user(
            email='test@novaedge.com',
            phone_number='+1234567890',
            first_name='John',
            last_name='Doe',
            country='USA',
            password='StrongPass123!',
            is_verified=True
        )
        
        url = reverse('login')
        wrong_data = {
            'email': 'test@novaedge.com',
            'password': 'WrongPassword'
        }
        
        # Try wrong password multiple times
        for i in range(6):
            response = self.client.post(url, wrong_data, format='json')
        
        # Check if user is locked
        user.refresh_from_db()
        self.assertTrue(user.is_locked())
        self.assertEqual(user.failed_login_attempts, 5)