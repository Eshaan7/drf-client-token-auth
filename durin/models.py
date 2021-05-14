import binascii
from os import urandom
from typing import Union

import humanize
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.utils.functional import cached_property

from durin.settings import durin_settings
from durin.signals import token_renewed
from durin.throttling import UserClientRateThrottle

User = settings.AUTH_USER_MODEL


def _create_token_string() -> str:
    return binascii.hexlify(
        urandom(int(durin_settings.TOKEN_CHARACTER_LENGTH / 2))
    ).decode()


class Client(models.Model):
    """
    Identifier to represent any API client/browser that consumes your RESTful API.
    """

    #: A unique identification name for the client.
    name = models.CharField(
        max_length=64,
        null=False,
        blank=False,
        db_index=True,
        unique=True,
        help_text=_("A unique identification name for the client."),
    )

    #: Token Time To Live (TTL) in timedelta. Format: ``DAYS HH:MM:SS``.
    token_ttl = models.DurationField(
        null=False,
        default=durin_settings.DEFAULT_TOKEN_TTL,
        verbose_name=_("Token Time To Live (TTL)"),
        help_text=_(
            """
            Token Time To Live (TTL) in timedelta. Format: <code>DAYS HH:MM:SS</code>.
            """
        ),
    )

    @cached_property
    def throttle_rate(self) -> Union[str, None]:
        if hasattr(self, "settings"):
            return self.settings.throttle_rate
        else:
            return None

    def __str__(self):
        td = humanize.naturaldelta(self.token_ttl)
        return "({0}, {1})".format(self.name, td)


class ClientSettings(models.Model):
    """
    It is recommended to subclass this model (and not :py:class:`~Client`)
    if you wish to add extra fields for storing any
    configuration or settings against ``Client`` instances.

    Reverse lookup: ``Client.settings``.

    .. versionadded:: 0.2
    """

    #: `OneToOneField <https://docs.djangoproject.com/en/3.2/topics/db/examples/one_to_one/>`__
    #: with :py:class:`~Client` with ``on_delete=models.CASCADE``.
    client = models.OneToOneField(
        Client,
        null=False,
        blank=False,
        related_name="settings",
        on_delete=models.CASCADE,
    )

    #: Throttle rate for requests authed with this client.
    #:
    #: **Format**: ``number_of_requests/period``
    #: where period should be one of: *('s', 'm', 'h', 'd')*.
    #: (same format as DRF's throttle rates)
    #:
    #: **Example**: ``100/h`` implies 100 requests each hour.
    throttle_rate = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name=_("Throttle rate for requests authed with this client"),
        help_text=_(
            """Follows the same format as DRF's throttle rates.
            Format: <em>'number_of_requests/period'</em>
            where period should be one of: ('s', 'm', 'h', 'd').
            Example: '100/h' implies 100 requests each hour.
            """
        ),
        validators=[UserClientRateThrottle.validate_client_throttle_rate],
    )

    def __str__(self):
        return "(rate: '{0}')".format(self.throttle_rate)


class UserClient(models.Model):
    """
    ``User`` <-> ``Client`` relationship.
    """

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "client"], name="unique user client pair"
            )
        ]

    # :class:`~User` ForeignKey
    user = models.ForeignKey(
        User,
        null=False,
        blank=False,
        related_name="clients",
        on_delete=models.CASCADE,
    )
    #: :class:`~Client` ForeignKey
    client = models.ForeignKey(
        Client,
        null=False,
        blank=False,
        related_name="users",
        on_delete=models.CASCADE,
    )

    def __str__(self) -> str:
        return "({0}, {1})".format(self.user, self.client)


class AuthTokenManager(models.Manager):
    def create(self, userclient: UserClient, delta_ttl: "timezone.timedelta" = None):
        token = _create_token_string()

        if delta_ttl is not None:
            expiry = timezone.now() + delta_ttl
        else:
            expiry = timezone.now() + userclient.client.token_ttl

        instance = super(AuthTokenManager, self).create(
            token=token,
            expiry=expiry,
            userclient=userclient,
        )
        return instance


class AuthToken(models.Model):
    """
    Token model with a unique constraint on ``User`` <-> ``Client`` relationship.
    """

    objects = AuthTokenManager()

    #: Token string
    token = models.CharField(
        max_length=durin_settings.TOKEN_CHARACTER_LENGTH,
        null=False,
        blank=False,
        db_index=True,
        unique=True,
        help_text=_("Token is auto-generated on save."),
    )
    #: Created time
    created = models.DateTimeField(auto_now_add=True)
    #: Expiry time
    expiry = models.DateTimeField(null=False)

    #: `OneToOneField <https://docs.djangoproject.com/en/3.2/topics/db/examples/one_to_one/>`__
    #: with :py:class:`~UserClient` with ``on_delete=models.CASCADE``.
    userclient = models.OneToOneField(
        UserClient,
        null=True,
        related_name="authtoken",
        on_delete=models.CASCADE,
    )

    def renew_token(self, renewed_by):
        """
        Utility function to renew the token.

        Updates the :py:attr:`~expiry` attribute by ``Client.token_ttl``.
        """
        new_expiry = timezone.now() + self.userclient.client.token_ttl
        self.expiry = new_expiry
        self.save(update_fields=("expiry",))
        token_renewed.send(
            sender=renewed_by,
            token=self,
            new_expiry=new_expiry,
        )
        return new_expiry

    @property
    def expires_in(self) -> str:
        """
        Dynamic property that gives the :py:attr:`~expiry`
        attribute in human readable string format.

        Uses `humanize package <https://github.com/jmoiron/humanize>`__.
        """
        if self.expiry:
            td = self.expiry - self.created
            return humanize.naturaldelta(td)
        else:
            return "N/A"

    @property
    def has_expired(self) -> bool:
        """
        Dynamic property that returns ``True`` if token has expired,
        otherwise ``False``.
        """
        return timezone.now() > self.expiry

    def __str__(self) -> str:
        return "({0}, {1})".format(self.token, self.userclient)
