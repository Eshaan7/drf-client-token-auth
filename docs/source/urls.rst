URLs (``durin.urls``)
========================

Durin provides a URL config ready with its 4 default views routed.

This can easily be included in your url config:

.. code-block:: python
  :linenos:
  :emphasize-lines: 3

  urlpatterns = [
    #...snip...
    url(r'api/auth/', include('durin.urls'))
    #...snip...
  ]

**Note**: It is important to use the string syntax and not try to import ``durin.urls``,
as the reference to the ``User`` model will cause the app to fail at import time.

The views would then accessible as:

- ``/api/auth/login`` -> ``LoginView``
- ``/api/auth/refresh`` - ``RefreshView``
- ``/api/auth/logout`` -> ``LogoutView``
- ``/api/auth/logoutall`` -> ``LogoutAllView``
- ``/api/auth/sessions`` -> ``TokenSessionsViewSet``
- ``/api/auth/apiaccess`` -> ``APIAccessTokenView``

they can also be looked up by name::

    from django.urls import reverse

    reverse('durin_login')
    reverse('durin_logout')
    reverse('durin_refresh')
    reverse('durin_logoutall')
    reverse('durin_tokensessions-list')
    reverse('durin_apiaccess')