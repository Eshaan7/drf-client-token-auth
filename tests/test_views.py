import time
from datetime import timedelta
from importlib import reload

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.serializers import DateTimeField

from durin import serializers, views
from durin.models import AuthToken, Client
from durin.serializers import UserSerializer
from durin.settings import durin_settings
from durin.signals import token_expired, token_renewed

from . import CustomTestCase

login_url = reverse("durin_login")
logout_url = reverse("durin_logout")
logoutall_url = reverse("durin_logoutall")
refresh_url = reverse("durin_refresh")
sessions_list_uri = reverse("durin_tokensessions-list")
apiaccess_uri = reverse("durin_apiaccess")

root_url = reverse("api-root")
cached_auth_url = reverse("cached-auth-api")
throttled_view_url = reverse("throttled-api")

new_settings = durin_settings.defaults.copy()
new_settings["API_ACCESS_CLIENT_NAME"] = "sessionsapiaccesstestcase_client"


class ViewsTestCase(CustomTestCase):
    def test_create_tokens_for_users(self):
        AuthToken.objects.all().delete()
        self.assertEqual(AuthToken.objects.count(), 0)
        self._create_clients()

        creds = self.creds.copy()
        creds2 = self.creds2.copy()
        for c in Client.objects.all():
            creds["client"] = c.name
            creds2["client"] = c.name
            # for user #1
            self.client.post(
                login_url,
                creds,
                format="json",
            )
            # for user #2
            self.client.post(
                login_url,
                creds2,
                format="json",
            )

        self.assertEqual(self.user.auth_token_set.count(), Client.objects.count())
        self.assertEqual(self.user2.auth_token_set.count(), Client.objects.count())
        self.assertTrue(all(t.token for t in AuthToken.objects.all()))

    def test_expired_token_fails(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        instance = AuthToken.objects.create(
            self.user, self.authclient, delta_ttl=timedelta(seconds=0)
        )
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % instance.token))
        response = self.client.get(root_url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data, {"detail": "The given token has expired."})

    def test_invalid_token_length_returns_401_code(self):
        invalid_token = "1" * (durin_settings.TOKEN_CHARACTER_LENGTH - 1)
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % invalid_token))
        response = self.client.get(root_url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data, {"detail": "Invalid token."})

    def test_invalid_odd_length_token_returns_401_code(self):
        self.assertEqual(Client.objects.count(), 1)
        instance = AuthToken.objects.create(self.user, self.authclient)
        odd_length_token = instance.token + "1"
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % odd_length_token))
        response = self.client.get(root_url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data, {"detail": "Invalid token."})

    def test_expiry_signals(self):
        self.signal_was_called = False

        def handler(sender, **kwargs):
            self.signal_was_called = True

        token_expired.connect(handler)

        instance = AuthToken.objects.create(
            user=self.user, client=self.authclient, delta_ttl=timedelta(seconds=0)
        )
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % instance.token))
        self.client.get(root_url)

        self.assertTrue(self.signal_was_called)

    def test_invalid_auth_prefix_return_401(self):
        instance = AuthToken.objects.create(user=self.user, client=self.authclient)
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % instance.token))
        ok_response = self.client.get(root_url)
        self.client.credentials(HTTP_AUTHORIZATION=("Baerer %s" % instance.token))
        failed_response = self.client.get(root_url)
        self.assertEqual(ok_response.status_code, 200)
        self.assertEqual(failed_response.status_code, 401)

    def test_invalid_auth_header_return_401(self):
        instance = AuthToken.objects.create(user=self.user, client=self.authclient)
        self.client.credentials(HTTP_AUTHORIZATION=("Token"))
        resp1 = self.client.get(root_url)
        self.assertEqual(resp1.status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s typo" % instance.token))
        resp2 = self.client.get(root_url)
        self.assertEqual(resp2.status_code, 401)


class AuthViewsTestCase(CustomTestCase):
    def test_login_returns_serialized_token(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        response = self.client.post(
            login_url,
            self.creds,
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(durin_settings.USER_SERIALIZER, None)
        self.assertIn("token", response.data)
        self.assertNotIn("user", response.data)
        self.assertNotIn(self.user.USERNAME_FIELD, response.data)

    def test_login_returns_serialized_token_and_username_field(self):
        new_settings["USER_SERIALIZER"] = UserSerializer
        with override_settings(REST_DURIN=new_settings):
            reload(views)
            self.assertEqual(AuthToken.objects.count(), 0)
            response = self.client.post(login_url, self.creds, format="json")
            self.assertEqual(new_settings["USER_SERIALIZER"], UserSerializer)
        reload(views)
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        username_field = self.user.USERNAME_FIELD
        self.assertIn("user", response.data)
        self.assertIn(username_field, response.data["user"])

    def test_login_returns_configured_expiry_datetime_format(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        EXPIRY_DATETIME_FORMAT = "%H:%M %d/%m/%y"
        new_settings["EXPIRY_DATETIME_FORMAT"] = EXPIRY_DATETIME_FORMAT
        with override_settings(REST_DURIN=new_settings):
            reload(views)
            self.assertEqual(
                new_settings["EXPIRY_DATETIME_FORMAT"],
                EXPIRY_DATETIME_FORMAT,
            )
            response = self.client.post(login_url, self.creds, format="json")

        reload(views)
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertNotIn("user", response.data)
        self.assertEqual(
            response.data["expiry"],
            DateTimeField(format=EXPIRY_DATETIME_FORMAT).to_representation(
                AuthToken.objects.first().expiry
            ),
        )

    def test_login_expiry_is_present(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        response = self.client.post(login_url, self.creds, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertIn("expiry", response.data)
        self.assertEqual(
            response.data["expiry"],
            DateTimeField().to_representation(AuthToken.objects.first().expiry),
        )

    def test_login_should_fail_if_no_client(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        self.creds.pop("client")
        response = self.client.post(login_url, self.creds)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "No client specified.")

    def test_login_should_fail_if_invalid_client(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        self.creds["client"] = "invalid name"
        response = self.client.post(login_url, self.creds)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "No client with that name.")

    def test_logout_deletes_keys(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        instance = AuthToken.objects.create(user=self.user, client=self.authclient)
        AuthToken.objects.create(user=self.user2, client=self.authclient)
        self.assertEqual(AuthToken.objects.count(), 2)

        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % instance.token))
        self.client.post(logout_url)
        self.assertEqual(
            AuthToken.objects.count(), 1, "other tokens should remain after logout"
        )

    def test_logout_all_deletes_keys(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        self._create_clients()
        for c in Client.objects.all():
            token = AuthToken.objects.create(user=self.user, client=c)
        self.assertEqual(AuthToken.objects.count(), len(self.client_names))

        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % token))
        self.client.post(logoutall_url, {}, format="json")
        self.assertEqual(AuthToken.objects.count(), 0)

    def test_logout_all_deletes_only_targets_keys(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        self._create_clients()
        for c in Client.objects.all():
            instance = AuthToken.objects.create(user=self.user, client=c)
            AuthToken.objects.create(user=self.user2, client=c)
        # 2 x len(self.client_names) tokens were created
        self.assertEqual(AuthToken.objects.count(), 2 * len(self.client_names))

        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % instance.token))
        self.client.post(logoutall_url, {}, format="json")
        # now half of the tokens (for user #1) should have been deleted
        self.assertEqual(
            AuthToken.objects.count(),
            len(self.client_names),
            "tokens from other users should not be affected by logout all",
        )

    def test_login_same_token_existing_client(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        resp1 = self.client.post(login_url, self.creds, format="json")
        self.assertEqual(resp1.status_code, 200)
        self.assertIn("token", resp1.data)
        self.assertEqual(AuthToken.objects.count(), 1)
        resp2 = self.client.post(login_url, self.creds, format="json")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("token", resp2.data)
        self.assertEqual(
            AuthToken.objects.count(),
            1,
            "should renew token, instead of creating new.",
        )
        self.assertEqual(
            resp1.data["expiry"],
            resp2.data["expiry"],
            "token expiry should be same after login",
        )
        self.assertEqual(
            resp1.data["token"],
            resp2.data["token"],
            "login should return existing token",
        )

    def test_login_renew_token_existing_client(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        new_settings["REFRESH_TOKEN_ON_LOGIN"] = True
        with override_settings(REST_DURIN=new_settings):
            reload(views)
            resp1 = self.client.post(login_url, self.creds, format="json")
            self.assertEqual(resp1.status_code, 200)
            self.assertIn("token", resp1.data)
            resp2 = self.client.post(login_url, self.creds, format="json")
            self.assertEqual(resp2.status_code, 200)
            self.assertIn("token", resp2.data)

        reload(views)
        self.assertEqual(
            AuthToken.objects.count(),
            1,
            "should renew token, instead of creating new.",
        )
        self.assertNotEqual(
            resp1.data["expiry"],
            resp2.data["expiry"],
            "token expiry should be renewed after login",
        )
        self.assertEqual(
            resp1.data["token"],
            resp2.data["token"],
            "token key must remain same",
        )

    def test_refresh_view_and_renewed_signal(self):
        self.signal_was_called = False

        def handler(sender, **kwargs):
            self.signal_was_called = True

        token_renewed.connect(handler)

        self.assertEqual(AuthToken.objects.count(), 0)
        instance = AuthToken.objects.create(user=self.user, client=self.authclient)
        self.assertEqual(AuthToken.objects.count(), 1)
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % instance.token))
        resp = self.client.post(refresh_url, {}, format="json")
        self.assertEqual(
            AuthToken.objects.count(), 1, "refresh view should not create new token."
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("expiry", resp.data)
        self.assertNotEqual(resp.data["expiry"], instance.expiry)
        self.assertTrue(self.signal_was_called, "token_renewed signal was called.")


@override_settings(REST_DURIN=new_settings)
class SessionAndAPIAccessViewsTestCase(CustomTestCase):
    def setUp(self):
        super(SessionAndAPIAccessViewsTestCase, self).setUp()
        # setup token and api client
        self.token = self._create_authtoken()
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % self.token.token))
        # setup apiaccess client
        self.apiaccess_client, _ = Client.objects.get_or_create(
            name=new_settings["API_ACCESS_CLIENT_NAME"]
        )

    # unit testcases for /sessions

    def test_sessions_list_200(self):
        # db assertions
        self.assertEqual(
            1,
            AuthToken.objects.filter(user=self.user).count(),
            msg="single instance exists",
        )

        response = self.client.get(sessions_list_uri)
        content = response.json()
        msg = (response, content)
        # response assertions
        self.assertEqual(200, response.status_code, msg=msg)
        self.assertNotIn("token", content[0], msg="token is omitted from view")
        self.assertNotIn("user", content[0], msg="user is omitted from view")

    def test_sessions_list_exclude_apiaccess_200(self):
        # create apiaccess token
        _ = self._create_authtoken(client_name=new_settings["API_ACCESS_CLIENT_NAME"])

        # db assertions
        self.assertEqual(
            2,
            AuthToken.objects.filter(user=self.user).count(),
            msg="two instance exists",
        )

        # 1. override settings to exclude token
        new_settings["API_ACCESS_EXCLUDE_FROM_SESSIONS"] = False
        with override_settings(REST_DURIN=new_settings):
            reload(views)
            response = self.client.get(sessions_list_uri)
            content = response.json()
            # response assertions
            self.assertEqual(200, response.status_code, msg=(response, content))
            self.assertEqual(2, len(content), msg="got 2 tokens")

        # 2. override settings to include token
        new_settings["API_ACCESS_EXCLUDE_FROM_SESSIONS"] = True
        with override_settings(REST_DURIN=new_settings):
            reload(views)
            response = self.client.get(sessions_list_uri)
            content = response.json()
            # response assertions
            self.assertEqual(200, response.status_code, msg=(response, content))
            self.assertEqual(1, len(content), msg="got 1 token")

        reload(views)

    def test_sessions_delete_204(self):
        newtoken = self._create_authtoken(client_name="test_sessions_delete_204")

        # db assertions
        self.assertEqual(
            2,
            AuthToken.objects.filter(user=self.user).count(),
            msg="two instances exists",
        )

        # request to delete this newtoken
        uri = reverse("durin_tokensessions-detail", args=[newtoken.pk])
        response = self.client.delete(uri)

        # response assertions
        self.assertEqual(204, response.status_code, msg=(response,))
        # db assertions
        self.assertEqual(
            1,
            AuthToken.objects.filter(user=self.user).count(),
            msg=(response, "2nd instance was deleted so single instance exists"),
        )

    def test_sessions_cant_delete_current_400(self):
        # request to delete token created in `setUp`
        uri = reverse("durin_tokensessions-detail", args=[self.token.pk])
        response = self.client.delete(uri)
        content = response.json()
        msg = (response, content, "raises ValidationError")

        # response assertions
        self.assertEqual(400, response.status_code, msg=msg)

    # unit testcases for /apiaccess

    def test_apiaccess_get_200(self):
        # create apiaccess token
        apiaccesstoken = self._create_authtoken(
            client_name=new_settings["API_ACCESS_CLIENT_NAME"]
        )

        # 1. override settings to exclude token
        new_settings["API_ACCESS_RESPONSE_INCLUDE_TOKEN"] = False
        with override_settings(REST_DURIN=new_settings):
            reload(serializers)
            reload(views)
            response = self.client.get(apiaccess_uri)
            content = response.json()
            # response assertions
            self.assertEqual(200, response.status_code, msg=(response, content))
            self.assertNotIn("token", content, msg="token is omitted from view")

        # 2. override settings to include token
        new_settings["API_ACCESS_RESPONSE_INCLUDE_TOKEN"] = True
        with override_settings(REST_DURIN=new_settings):
            reload(serializers)
            reload(views)
            response = self.client.get(apiaccess_uri)
            content = response.json()
            # response assertions
            self.assertEqual(200, response.status_code, msg=(response, content))
            self.assertEqual(
                apiaccesstoken.token,
                content["token"],
                msg="tokens from db and view must match",
            )

        reload(serializers)
        reload(views)

    def test_apiaccess_get_404(self):
        response = self.client.get(apiaccess_uri)
        content = response.json()
        # response assertions
        self.assertEqual(
            404, response.status_code, msg="because no apiaccess token exists"
        )
        self.assertDictEqual({"detail": "Not found."}, content, msg="not found")

    def test_apiaccess_post_201(self):
        response = self.client.post(apiaccess_uri)
        content = response.json()
        msg = (response, content, "apiaccess token must be created")

        # response assertions
        self.assertEqual(201, response.status_code, msg=msg)

        # assert against db value
        newtoken = AuthToken.objects.get(
            user=self.user, client__name=new_settings["API_ACCESS_CLIENT_NAME"]
        )
        self.assertEqual(
            newtoken.token, content["token"], msg="tokens from db and view must match"
        )

    def test_apiaccess_post_already_exists_400(self):
        response = self.client.post(apiaccess_uri)

        # response assertions
        self.assertEqual(
            201,
            response.status_code,
            msg=(
                response,
                response.json(),
                "In 1st request, apiaccess token must be created",
            ),
        )

        response = self.client.post(apiaccess_uri)

        # response assertions
        self.assertEqual(
            400,
            response.status_code,
            msg=(
                response,
                response.json(),
                """
                In 2nd request,
                `ValidationError` is raised because apiaccess token already exists
                """,
            ),
        )

    def test_apiaccess_delete_204(self):
        reload(views)  # otherwise fails
        # create apiaccess token
        apiaccesstoken = self._create_authtoken(
            client_name=new_settings["API_ACCESS_CLIENT_NAME"]
        )
        # request to delete this apiaccesstoken
        response = self.client.delete(apiaccess_uri)

        # response assertions
        self.assertEqual(204, response.status_code, msg=(response,))

        with self.assertRaises(AuthToken.DoesNotExist, msg="token was deleted"):
            AuthToken.objects.get(token=apiaccesstoken.token)

    def test_apiaccess_delete_404(self):
        # request to delete apiaccess token when it doesn't exist
        response = self.client.delete(apiaccess_uri)
        content = response.json()

        # response assertions
        self.assertEqual(
            404, response.status_code, msg="because no apiaccess token exists"
        )
        self.assertDictEqual({"detail": "Not found."}, content, msg="not found")


class ExampleProjectViewsTestCase(CustomTestCase):
    def test_cached_api(self):
        self.assertEqual(AuthToken.objects.count(), 0)
        instance = AuthToken.objects.create(
            self.user, self.authclient, delta_ttl=timedelta(seconds=1)
        )
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % instance.token))
        resp1 = self.client.get(cached_auth_url)
        self.assertEqual(resp1.status_code, 200)
        time.sleep(3)
        self.assertTrue(instance.has_expired, "token expiry was set to 1 second.")
        resp2 = self.client.get(cached_auth_url)
        self.assertEqual(
            resp2.status_code,
            200,
            "token state was cached even though token has expired.",
        )

    def test_throttled_api_default_rate_429(self):
        """
        Default rate in example_project is: {"user_per_client": "2/m"}
        """
        self.assertEqual(AuthToken.objects.count(), 0)
        instance = AuthToken.objects.create(self.user, self.authclient)
        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % instance.token))

        resp1 = self.client.get(throttled_view_url)
        self.assertEqual(resp1.status_code, 200)

        resp2 = self.client.get(throttled_view_url)
        self.assertEqual(resp2.status_code, 200)

        resp3 = self.client.get(throttled_view_url)
        self.assertEqual(
            resp3.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
            msg="Third request within the minute gets throttled",
        )

    def test_throttled_api_custom_rate_429(self):
        THROTTLE_NUM_REQUESTS = 5

        testauthclient = Client.objects.create(
            name="test_throttled_api_custom_rate_429",
            throttle_rate="{0}/m".format(THROTTLE_NUM_REQUESTS),
        )
        instance = AuthToken.objects.create(self.user, testauthclient)
        self.assertEqual(AuthToken.objects.count(), 1)

        self.client.credentials(HTTP_AUTHORIZATION=("Token %s" % instance.token))

        for _ in range(THROTTLE_NUM_REQUESTS):
            resp = self.client.get(throttled_view_url)
            self.assertEqual(resp.status_code, 200)

        resp = self.client.get(throttled_view_url)
        self.assertEqual(
            resp.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
            msg="6th request within the minute gets throttled",
        )

    def test_throttled_api_no_token_401(self):
        resp = self.client.get(throttled_view_url)
        self.assertEqual(
            resp.status_code,
            status.HTTP_401_UNAUTHORIZED,
            msg="No token was set",
        )
