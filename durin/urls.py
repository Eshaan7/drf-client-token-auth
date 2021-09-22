from django.urls import include, path
from rest_framework import routers

from durin import views

router = routers.SimpleRouter(trailing_slash=False)
router.register(
    r"sessions/", views.TokenSessionsViewSet, basename="durin_tokensessions"
)


urlpatterns = [
    path("login/", views.LoginView.as_view(), name="durin_login"),
    path("refresh/", views.RefreshView.as_view(), name="durin_refresh"),
    path("logout/", views.LogoutView.as_view(), name="durin_logout"),
    path("logoutall/", views.LogoutAllView.as_view(), name="durin_logoutall"),
    path("apiaccess/", views.APIAccessTokenView.as_view(), name="durin_apiaccess"),
    # router URLs
    path("", include(router.urls)),
]
