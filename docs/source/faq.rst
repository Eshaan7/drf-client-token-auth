FAQ: Why use durin over JWT or other libraries ?
=================================================

Good question.

Authentication is tricky. There are many libraries available for DRF which provide token authentication. 
I've personally used `drf-simplejwt <https://django-rest-framework-simplejwt.readthedocs.io/>`__ 
and `django-rest-knox <http://james1345.github.io/django-rest-knox/>`__ and they are both great at their `implementation`.

**So why would you want to use Django-Rest-Durin ?**

Here are a few use cases which I needed (and why it lead me to create durin) 
and might help you make a better decision too,

- If you'd like to use Django's Admin interface to manage the different clients which consume your API.
- If you want the token expiration to be dependent on what API client it is meant for. 
  For example, you might want to create tokens which never expire for a Command Line Client but want a shorter expiry for a JavaScript (web) client.
- If you want to limit number of tokens allowed per user.
- If you'd like to refresh token expiry without changing token key.
- If you or your organization are interested in Client Level Analytics such as keeping track of which user uses what client the most, etc.
- If you want to restrict certian ``APIView`` or ``Viewsets`` to allow authenticated requests from only specific clients of your choice.

.... and more. Make a PR on GitHub to tell us what you use durin for!