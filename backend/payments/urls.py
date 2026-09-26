from django.urls import path

from payments import views

urlpatterns = [
    path("connect/", views.connect, name="stripe-connect"),
    path("connect/status/", views.connect_status, name="stripe-connect-status"),
    path("connect/login-link/", views.connect_login_link, name="stripe-connect-login"),
    path("connect/return/", views.connect_return, name="stripe-connect-return"),
    path("connect/refresh/", views.connect_refresh, name="stripe-connect-refresh"),
    path("sales/", views.sales, name="stripe-sales"),
    path("sales/<int:sale_id>/authorize/", views.sale_authorize, name="stripe-sale-authorize"),
    path("sales/<int:sale_id>/transfer/", views.sale_transfer, name="stripe-sale-transfer"),
    path("webhook/", views.webhook, name="stripe-webhook"),
]
