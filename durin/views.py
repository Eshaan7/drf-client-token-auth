from datetime import datetime

from django.contrib.auth.signals import user_logged_in, user_logged_out
from rest_framework import mixins, status
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.serializers import DateTimeField
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from .auth import TokenAuthentication
from .models import AuthToken, Client
from .serializers import APIAccessTokenSerializer, TokenSessionsSerializer
from .settings import durin_settings


class LoginView(APIView):
    """Durin's Login View.\n
    This view will return a JSON response when valid ``username``, ``password`` and
    (if not overwritten) ``client`` fields are POSTed to the view using
    form data or JSON.

    It uses the default serializer provided by
    Django-Rest-Framework (``rest_framework.authtoken.serializers.AuthTokenSerializer``)
    to validate the user credentials.

    It is possible to customize LoginView behaviour by overriding the following
    helper methods:
    """

    authentication_classes = []
    permission_classes = []

    def get_context(self):
        """
        to change the context passed to the ``UserSerializer``.
        """
        return {"request": self.request, "format": self.format_kwarg, "view": self}

    @staticmethod
    def validate_and_return_user(request):
        serializer = AuthTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data["user"]

    def get_client_obj(self, request) -> "Client":
        """
        To get and return the associated :class:`durin.models.Client` object.

        :raises rest_framework.exceptions.ValidationError
        """
        client_name = request.data.get("client", None)
        if not client_name:
            raise ValidationError({"detail": "No client specified."})

        try:
            return Client.objects.get(name=client_name)
        except Client.DoesNotExist:
            raise ValidationError({"detail": "No client with that name."})

    def get_token_obj(self, request, client: "Client") -> "AuthToken":
        """
        Flow used to return the :class:`durin.models.AuthToken` object.
        """
        try:
            # if a token for this user-client pair already exists,
            # we can just return it
            token = AuthToken.objects.get(user=request.user, client=client)
            if durin_settings.REFRESH_TOKEN_ON_LOGIN:
                self.renew_token(request=request, token=token)
        except AuthToken.DoesNotExist:
            # create new token
            token = AuthToken.objects.create(request.user, client)

        return token

    def renew_token(self, request, token: "AuthToken") -> None:
        """
        How to renew the token instance in case
        ``settings.REFRESH_TOKEN_ON_LOGIN`` is set to ``True``.
        """
        token.renew_token(request=request)

    @staticmethod
    def format_expiry_datetime(expiry: "datetime") -> str:
        """
        To format the expiry ``datetime`` object at your convenience.
        """
        datetime_format = durin_settings.EXPIRY_DATETIME_FORMAT
        return DateTimeField(format=datetime_format).to_representation(expiry)

    def get_user_serializer_class(self):
        """
        To change the class used for serializing the user.
        """
        return durin_settings.USER_SERIALIZER

    def get_post_response_data(self, request, token_obj: "AuthToken") -> dict:
        """
        Override this to return a fully customized payload.
        """
        UserSerializer = self.get_user_serializer_class()
        data = {
            "expiry": self.format_expiry_datetime(token_obj.expiry),
            "token": token_obj.token,
        }
        if UserSerializer is not None:
            data["user"] = UserSerializer(request.user, context=self.get_context()).data
        return data

    def post(self, request, *args, **kwargs):
        request.user = self.validate_and_return_user(request)
        client = self.get_client_obj(request)
        token_obj = self.get_token_obj(request, client)
        user_logged_in.send(
            sender=request.user.__class__, request=request, user=request.user
        )
        data = self.get_post_response_data(request, token_obj)
        return Response(data)


class RefreshView(APIView):
    """Durin's Refresh View\n
    This view accepts only a post request with an empty body.
    It responds to Durin Token Authentication. On a successful request,

    1. The given token's expiry is extended by it's associated
       :py:attr:`durin.models.Client.token_ttl`
       duration and a JSON object will be returned containing a single ``expiry``
       key as the new timestamp for when the token expires.

    2. :meth:`durin.signals.token_renewed` is called.
    """

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    @staticmethod
    def format_expiry_datetime(expiry: "datetime") -> str:
        """
        To format the expiry ``datetime`` object at your convenience.
        """
        datetime_format = durin_settings.EXPIRY_DATETIME_FORMAT
        return DateTimeField(format=datetime_format).to_representation(expiry)

    def renew_token(self, request, token: "AuthToken") -> "datetime":
        """
        How to renew the token instance.
        """
        new_expiry = token.renew_token(request=request)
        return new_expiry

    def post(self, request, *args, **kwargs):
        auth_token = request._auth
        new_expiry = self.renew_token(request=request, token=auth_token)
        new_expiry_repr = self.format_expiry_datetime(new_expiry)
        return Response({"expiry": new_expiry_repr}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Durin's Logout View.\n
    This view accepts only a post request with an empty body.
    It responds to Durin Token Authentication. On a successful request,

    1. The token used to authenticate is deleted from
       the database and can no longer be used to authenticate.

    2. :meth:`django.contrib.auth.signals.user_logged_out` is called.

    :returns: 204 (No content)
    """

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        request._auth.delete()
        user_logged_out.send(
            sender=request.user.__class__, request=request, user=request.user
        )
        return Response(None, status=status.HTTP_204_NO_CONTENT)


class LogoutAllView(APIView):
    """Durin's LogoutAllView.\n
    This view accepts only a post request with an empty body. It responds to Durin Token
    Authentication.
    On a successful request,

    1. The token used to authenticate, and **all other tokens**
       registered to the same ``User`` account, are deleted from the
       system and can no longer be used to authenticate.

    2. :meth:`django.contrib.auth.signals.user_logged_out` is called.

    :returns: 204 (No content)
    """

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        request.user.auth_token_set.all().delete()
        user_logged_out.send(
            sender=request.user.__class__, request=request, user=request.user
        )
        return Response(None, status=status.HTTP_204_NO_CONTENT)


class TokenSessionsViewSet(
    mixins.ListModelMixin, mixins.DestroyModelMixin, GenericViewSet
):
    """Durin's TokenSessionsViewSet.\n
    - Returns list of active sessions of authed user.
    - Only ``list()`` and ``delete()`` operations.
    """

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    queryset = AuthToken.objects.select_related("client").all()
    serializer_class = TokenSessionsSerializer
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        # filter against authed user
        qs = qs.filter(user=self.request.user)
        # exclude session for the APIAccess session
        # if `API_ACCESS_EXCLUDE_FROM_SESSIONS` setting is True
        if durin_settings.API_ACCESS_EXCLUDE_FROM_SESSIONS:
            qs = qs.exclude(client__name=durin_settings.API_ACCESS_CLIENT_NAME)
        return qs

    def perform_destroy(self, instance):
        """
        Overwrite to prevent deletion of object
        against which current request was authed.
        """
        if instance.pk == self.request.auth.pk:
            raise ValidationError(
                "Can't delete token if the request is authed with it."
                "Use {} instead.".format(reverse("durin_logout"))
            )
        instance.delete()


class APIAccessTokenView(APIView):
    """Durin's APIAccessTokenView.\n"""

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    @property
    def client_name(self) -> str:
        client_name = getattr(durin_settings, "API_ACCESS_CLIENT_NAME", None)
        # verify/ asssert
        assert client_name, "setting `API_ACCESS_CLIENT_NAME` must be set to use this."
        return client_name

    def get_serializer(self, *args, **kwargs):
        return APIAccessTokenSerializer(
            *args,
            **kwargs,
            context={
                "request": self.request,
                "format": self.format_kwarg,
                "view": self,
                "client_name": self.client_name,
            },
        )

    def get_object(self):
        try:
            instance = AuthToken.objects.get(
                user__pk=self.request.user.pk,
                client__name=self.client_name,
            )
        except AuthToken.DoesNotExist:
            raise NotFound()

        return instance

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def post(self, request):
        serializer = self.get_serializer(data={})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
