"""
Django-stomp's public API for handling subscriptions with STOMP 1.1.
"""
from typing import Any
from typing import Callable
from typing import Optional

from django_stomp.services.subscribe.stomp11.builder import create_listener_stomp11
from django_stomp.settings.types import StompSettings


def subscribe_forever(
    subscription_callback: Callable, settings: StompSettings, param_to_callback: Optional[Any] = None
):
    """
    Appends a new listener to a destination using STOMP 1.1 protocol version.
    """
    listener = create_listener_stomp11(subscription_callback, settings, param_to_callback)

    listener.subscribe()


def subscribe_temporarily(
    subscription_callback: Callable,
    settings: StompSettings,
    subscription_duration: float = 1.0,
    param_to_callback: Optional[Any] = None,
):
    """
    Appends a new listener to a destination using STOMP 1.1 protocol version for fixed amount of time (defaults to 1s).
    """
    listener = create_listener_stomp11(subscription_callback, settings, param_to_callback)

    listener.subscribe(block_main_thread_period=subscription_duration)
