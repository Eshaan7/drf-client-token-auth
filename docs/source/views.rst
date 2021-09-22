Views (``durin.views``)
================================

Durin provides four views that handle token management for you.
And two additional views to allow sessions management.

Auth Management Views
###########

--------------------------

LoginView
--------------------------

.. autoclass:: durin.views.LoginView
   :members:
   :show-inheritance:

Response Data and User Serialization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When the endpoint authenticates a request, a JSON object will be returned
containing the ``token`` as a string, ``expiry`` as a timestamp for when
the token expires.

This is because ``USER_SERIALIZER`` setting is ``None`` by default.

If you wish to return custom data upon successful authentication
like ``first_name``, ``last_name``, and ``username`` then the included ``UserSerializer``
class can be used inside ``REST_DURIN`` settings by adding :class:`durin.serializers.UserSerializer`.

Obviously, if your app uses a custom user model that does not have these fields,
a custom serializer must be used.

Client Configuration
^^^^^^^^^^^^^^^^^^^^

In most cases, you would want to customize how the login view gets the 
client object to associate with the token. By default, it is the ``client`` attribute in POSTed request body. 
Here's an example snippet of how you can override this behaviour::

        ### views.py:

        from durin.models import Client as APIClient
        from durin.views import LoginView as DurinLoginView

        class LoginView(DurinLoginView):

            @staticmethod
            def get_client_obj(request):
                # get the client's name from a request header
                client_name = request.META.get("X-my-personal-header", None)
                if not client_name:
                    raise ParseError("No client specified.", status.HTTP_400_BAD_REQUEST)
                return APIClient.objects.get_or_create(name=client_name)


        ### urls.py:

        from durin import views as durin_views
        from yourapp.views import LoginView

        urlpatterns = [
            url(r'login/', LoginView.as_view(), name='durin_login'),
            url(r'refresh/', durin_views.RefreshView.as_view(), name='durin_refresh'),
            url(r'logout/', durin_views.LogoutView.as_view(), name='durin_logout'),
            url(r'logoutall/', durin_views.LogoutAllView.as_view(), name='durin_logoutall'),
        ]

--------------------------

RefreshView
--------------------------

.. autoclass:: durin.views.RefreshView
   :members:
   :show-inheritance:

--------------------------

LogoutView
--------------------------

.. autoclass:: durin.views.LogoutView
   :show-inheritance:

--------------------------

LogoutAllView
--------------------------

.. autoclass:: durin.views.LogoutAllView
   :show-inheritance:

.. Note:: It is not recommended to alter the Logout views. They are designed 
          specifically for token management, and to respond to durin authentication.
          Modified forms of the class may cause unpredictable results.


Session Management Views
###########

--------------------------

TokenSessionsViewSet
--------------------------

.. autoclass:: durin.views.TokenSessionsViewSet
   :show-inheritance:

--------------------------

APIAccessTokenView
--------------------------

.. autoclass:: durin.views.APIAccessTokenView
   :show-inheritance:

--------------------------