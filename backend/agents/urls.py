from django.urls import path

from agents import views

urlpatterns = [
    path("salt/chat/", views.salt_chat, name="salt-chat"),
]
