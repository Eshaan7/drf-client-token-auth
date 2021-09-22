Settings (``durin.settings``)
================================

Settings in durin are handled in a similar way to the rest framework settings.
All settings are namespaced in the ``'REST_DURIN'`` setting.

Example ``settings.py``::

		#...snip...
		# These are the default values if none are set
		from datetime import timedelta
		from rest_framework.settings import api_settings
		REST_DURIN = {
			"DEFAULT_TOKEN_TTL": timedelta(days=1),
			"TOKEN_CHARACTER_LENGTH": 64,
			"USER_SERIALIZER": None,
			"AUTH_HEADER_PREFIX": "Token",
			"EXPIRY_DATETIME_FORMAT": api_settings.DATETIME_FORMAT,
			"TOKEN_CACHE_TIMEOUT": 60,
			"REFRESH_TOKEN_ON_LOGIN": False,
			"AUTHTOKEN_SELECT_RELATED_LIST": ["user"],
			"API_ACCESS_CLIENT_NAME": None,
			"API_ACCESS_EXCLUDE_FROM_SESSIONS": False,
			"API_ACCESS_RESPONSE_INCLUDE_TOKEN": False,
		}
		#...snip...

.. data:: DEFAULT_TOKEN_TTL
	
	Default: ``timedelta(days=1)``

	This is how long a token can exist before it expires. Expired tokens are automatically removed from the system.

	The setting should be set to an instance of ``datetime.timedelta``.

	Durin provides setting a different token Time To Live (``token_ttl``) value per client object. 
	So this is the default value the :class:`durin.models.Client` model uses incase a custom value wasn't specified.

	**Warning:** setting a 0 or negative timedelta will create tokens that instantly expire,
	the system will not prevent you setting this.

.. data:: TOKEN_CHARACTER_LENGTH
	
	Default: ``64``

	This is the length of the token that will be sent to the client. This shouldn't need changing.

.. data:: USER_SERIALIZER
	
	Default: ``None``

	This is the reference to the class used to serialize the ``User`` objects when
	succesfully returning from :class:`durin.views.LoginView`. The default is :class:`durin.serializers.UserSerializer`.

.. data:: AUTH_HEADER_PREFIX
	
	Default: ``"Token"``

	This is the Authorization header value prefix.

.. data:: EXPIRY_DATETIME_FORMAT
	
	Default: `DATETIME_FORMAT <https://www.django-rest-framework.org/api-guide/settings/#date-and-time-formatting>`__ 
	(of Django REST framework)

	This is the expiry datetime format returned in the login and refresh views.
	
	May be any of ``None``, ``iso-8601`` or a Python 
	`strftime format <https://docs.python.org/3/library/time.html#time.strftime>`__ string.

.. data:: TOKEN_CACHE_TIMEOUT
	
	Default: ``60``

	This is the cache timeout (in seconds) used by ``django-memoize`` 
	in case you are using :class:`durin.auth.CachedTokenAuthentication` backend in your app.

.. data:: REFRESH_TOKEN_ON_LOGIN
	
	Default: ``False``

	When a request is made to the :class:`durin.views.LoginView`. One of two things happen: 
	
	1. Token instance for a particular user-client pair already exists.
	
	2. A new token instance is generated for the provided user-client pair.

	In the first case, the already existing token is sent in response. 
	So this setting if set to ``True`` should extend the expiry time of the 
	token by it's :class:`durin.models.Client` ``token_ttl`` everytime login happens.

.. data:: AUTHTOKEN_SELECT_RELATED_LIST

	Default: ``["user"]``

	This is passed as an argument to ``select_related`` when the :class:`durin.auth.TokenAuthentication` class
	fetches the :class:`durin.models.AuthToken` instance. For example,

	.. code-block:: python

		AuthToken.objects.select_related(*AUTHTOKEN_SELECT_RELATED_LIST).get(token=token_string)

	Otherwise, set to a falsy value such as ``None`` or ``False`` to not use ``select_related``.

	.. Hint:: Refer to `Django's select_related docs <https://docs.djangoproject.com/en/3.2/ref/models/querysets/#select-related>`_
	          to see how this can boost performance by reducing number of SQL queries made.


.. data:: API_ACCESS_CLIENT_NAME

	Default: ``None``

	There may be an use-case where you want to issue API keys to your users so they can call your RESTful API
	using cURL or a custom client. 
	
	Set this setting to the ``name` of the specific :class:`durin.models.Client` instance to issue these API keys against.

	Note: The :class:`durin.views.APIAccessTokenView` view allows management of this.

.. data:: API_ACCESS_EXCLUDE_FROM_SESSIONS

	Default: ``False``

	If set to ``True``, the ``AuthToken`` instance for the specifc ``API_ACCESS_CLIENT_NAME``'s `Client`` instance
	will be excluded from the overall "Sessions List" 
	(``GET /api/sessions/``) response.

	This is useful because you may want the view to list only the "browser sessions".

.. data:: API_ACCESS_RESPONSE_INCLUDE_TOKEN

	Default: ``False``

	If set to ``False``, the ``token`` field would be omitted from the
	:class:`durin.views.APIAccessTokenView` view's (``GET /api/apiaccess/``) response.

	In case of ``POST`` request, the ``token`` field is always included despite of this setting.