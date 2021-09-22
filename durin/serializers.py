from django.contrib.auth import get_user_model
from rest_framework import serializers as rfs

from .models import AuthToken, Client
from .settings import durin_settings

User = get_user_model()
username_field = User.USERNAME_FIELD if hasattr(User, "USERNAME_FIELD") else "username"


class UserSerializer(rfs.ModelSerializer):
    class Meta:
        model = User
        fields = (username_field,)


class TokenSessionsSerializer(rfs.ModelSerializer):
    """
    Used in :class:`durin.views.TokenSessionsViewSet`.
    """

    class Meta:
        model = AuthToken
        fields = [
            "id",
            "client",
            "created",
            "expiry",
            "has_expired",
            "is_current",
            "expires_in_str",
        ]
        read_only_fields = [
            "token",
            "client",
            "user",
            "created",
            "expiry",
            "expires_in_str",
        ]

    client = rfs.SlugRelatedField(
        slug_field="name",
        read_only=True,
    )
    expires_in_str = rfs.CharField(source="expires_in")
    is_current = rfs.SerializerMethodField()

    def get_is_current(self, obj: AuthToken) -> bool:
        request = self.context["request"]
        return obj.pk == request.auth.pk


class APIAccessTokenSerializer(rfs.ModelSerializer):
    """
    Used in :class:`durin.views.APIAccessTokenView`.
    """

    class Meta:
        model = AuthToken
        fields = [
            "client",
            "created",
            "expiry",
            "has_expired",
            "expires_in_str",
        ]
        read_only_fields = [
            "token",
            "client",
            "user",
            "created",
            "expiry",
            "expires_in_str",
        ]

    client = rfs.SlugRelatedField(
        slug_field="name",
        read_only=True,
    )
    expires_in_str = rfs.CharField(source="expires_in", read_only=True)

    def get_field_names(self, declared_fields, info):
        """
        :meta private:
        """
        fields = super().get_field_names(declared_fields, info)
        if (
            durin_settings.API_ACCESS_RESPONSE_INCLUDE_TOKEN
            or self.context["request"].method.upper() == "POST"
        ):
            # only send token on POST/create request, or
            # if `API_ACCESS_RESPONSE_INCLUDE_TOKEN` setting is True
            fields.append("token")
        return fields

    def create(self, validated_data):
        """
        :meta private:
        """
        user = self.context["request"].user
        client_name = self.context["client_name"]
        if AuthToken.objects.filter(user=user, client__name=client_name).exists():
            raise rfs.ValidationError("An API token was already issued to you.")

        validated_data["user"] = user
        validated_data["client"] = Client.objects.get(name=client_name)
        return super().create(validated_data)
