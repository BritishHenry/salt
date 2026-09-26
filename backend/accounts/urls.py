from django.urls import path

from accounts import views

urlpatterns = [
    path("signup/", views.signup, name="account-signup"),
    path("login/", views.login, name="account-login"),
    path("logout/", views.logout, name="account-logout"),
    path("me/", views.me, name="account-me"),
    path("marketplaces/", views.marketplaces, name="account-marketplaces"),
    path("provision/", views.provision_account, name="account-provision"),
]
