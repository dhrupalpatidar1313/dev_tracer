from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

User = get_user_model()

class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_and_login(self):
        # 1. Register
        resp = self.client.post('/api/v1/auth/register/', {
            "username": "testuser",
            "password": "SecurePassword123!"
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('token', resp.json())
        self.assertEqual(resp.json()['user']['username'], 'testuser')
        self.assertEqual(resp.json()['user']['role'], 'viewer') # Check signal default role

        # 2. Login
        resp_login = self.client.post('/api/v1/auth/login/', {
            "username": "testuser",
            "password": "SecurePassword123!"
        }, format='json')
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn('token', resp_login.json())

        # 3. Me
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + resp_login.json()['token'])
        resp_me = self.client.get('/api/v1/auth/me/')
        self.assertEqual(resp_me.status_code, 200)
        self.assertEqual(resp_me.json()['username'], 'testuser')

        # 4. Logout
        resp_logout = self.client.post('/api/v1/auth/logout/')
        self.assertEqual(resp_logout.status_code, 204)

        # 5. Me again (should fail)
        resp_me_after = self.client.get('/api/v1/auth/me/')
        self.assertEqual(resp_me_after.status_code, 401)
