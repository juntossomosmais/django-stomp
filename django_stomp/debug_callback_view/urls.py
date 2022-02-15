from django.urls import path

from .views import debug_callback_view

urlpatterns = [
    path("debug-function/", debug_callback_view, name="debug-callback-view"),
]
