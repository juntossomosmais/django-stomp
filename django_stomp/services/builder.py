"""
Builder service for easily creating listeners and publishers.
"""

import logging
from typing import Callable

from django_stomp.exceptions import DjangoStompImproperlyConfigured
from django_stomp.services.listener import StompContext11
from django_stomp.services.listener import StompListener11
from django_stomp.settings.django_stomp import compile_django_stomp_settings
from django_stomp.settings.types import BrokerType

logger = logging.getLogger(__name__)


def create_listener_rabbitmq(callback: Callable, destination_name: str) -> StompListener11:
    """
    Builds a stomp listener for RabbitMQ broker.
    """
    settings = compile_django_stomp_settings(destination_name)
    if settings.broker_type != BrokerType.RABBITMQ:
        raise DjangoStompImproperlyConfigured("Broker vendor must be 'rabbitmq' to create a rabbitmq listener!")

    stomp_context = StompContext11(settings.connection_settings, settings.subscription_settings)
    return StompListener11(callback, stomp_context)


def create_listener_activemq(callback: Callable, destination_name: str) -> StompListener11:
    """
    Builds a stomp listener for RabbitMQ broker.
    """
    settings = compile_django_stomp_settings(destination_name)
    if settings.broker_type != BrokerType.ACTIVEMQ:
        raise DjangoStompImproperlyConfigured("Broker vendor must be 'activemq' to create an activemq listener!")

    stomp_context = StompContext11(settings.connection_settings, settings.subscription_settings)
    return StompListener11(callback, stomp_context)
