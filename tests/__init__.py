from django.contrib.auth import get_user_model
from django.core.cache import cache as default_cache
from rest_framework.test import APITestCase

from durin.models import AuthToken, Client

User = get_user_model()


class CustomTestCase(APITestCase):
    def setUp(self):
        # cleanup
        default_cache.clear()
        AuthToken.objects.all().delete()
        Client.objects.all().delete()
        # setup
        self.authclient = Client.objects.create(name="authclientfortest")
        username = "john.doe"
        email = "john.doe@example.com"
        password = "hunter2"
        self.user = User.objects.create_user(username, email, password)
        self.creds = {
            "username": username,
            "password": password,
            "client": self.authclient.name,
        }

        username2 = "jane.doe"
        email2 = "jane.doe@example.com"
        password2 = "hunter2"
        self.user2 = User.objects.create_user(username2, email2, password2)
        self.creds2 = {
            "username": username2,
            "password": password2,
            "client": self.authclient.name,
        }

        self.client_names = ["web", "mobile", "cli"]

    def _create_clients(self) -> None:
        Client.objects.all().delete()
        self.assertEqual(Client.objects.count(), 0)
        for name in self.client_names:
            Client.objects.create(name=name)
        self.assertEqual(Client.objects.count(), len(self.client_names))

    def _create_authtoken(self, user=None, client_name=None) -> AuthToken:
        if not user:
            user = self.user
        if not client_name:
            client_name = "customtestcase_client"
        client, _ = Client.objects.get_or_create(name=client_name)
        try:
            token = AuthToken.objects.get(user=user, client=client)
        except AuthToken.DoesNotExist:
            token = AuthToken.objects.create(user=user, client=client)
        return token
