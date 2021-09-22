from django.contrib import admin

from durin import models


@admin.register(models.AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    """Django's ModelAdmin for AuthToken.\n
    In most cases, you would want to override this to make
    ``AuthTokenAdmin.raw_id_fields = ("user",)``
    """

    list_select_related = True

    list_display = (
        "token",
        "client",
        "user",
        "created",
        "expires_in",
    )
    list_filter = ("client__name", "user")

    readonly_fields = ("token", "expiry", "created", "expires_in")

    def get_fieldsets(self, request, obj=None):
        """
        Hook for specifying fieldsets.

        :meta private:
        """
        if not obj:
            return [
                (
                    "API Auth Token",
                    {
                        "fields": (
                            "user",
                            "client",
                        ),
                        "description": """
                    <h3>Token will be auto-generated on save.</h3>
                    <h3>Token will carry the same expiry as the
                     selected client's token TTL.</h3>
                """,
                    },
                ),
            ]
        else:
            return super().get_fieldsets(request, obj)

    def has_change_permission(self, request, obj=None):
        """
        :meta private:
        """
        return False

    def save_model(self, request, obj, form, change):
        """
        Given a model instance save it to the database.

        :meta private:
        """
        if not change:
            created_obj = models.AuthToken.objects.create(
                user=obj.user, client=obj.client
            )
            obj.pk = created_obj.pk
            obj.token = created_obj.token
            obj.expiry = created_obj.expiry
        else:
            super(AuthTokenAdmin, self).save_model(request, obj, form, change)


@admin.register(models.Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Django's ModelAdmin for :class:`Client` model.
    """

    list_display = (
        "id",
        "name",
        "token_ttl",
        "throttle_rate",
    )
