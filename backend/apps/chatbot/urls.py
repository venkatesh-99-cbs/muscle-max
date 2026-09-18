from django.urls import path

from apps.chatbot.views import ChatAskView

urlpatterns = [
    path("ask/", ChatAskView.as_view(), name="chatbot-ask"),
]
