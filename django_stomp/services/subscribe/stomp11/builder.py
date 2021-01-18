"""
Builder service for easily creating listeners and publishers.
"""

import logging
from typing import Any
from typing import Callable
from typing import Optional

from django_stomp.exceptions import DjangoStompImproperlyConfigured
from django_stomp.services.subscribe.stomp11.adapter import BrokerAdapterRabbitMQ
from django_stomp.services.subscribe.stomp11.callback import subscription_callback_factory
from django_stomp.services.subscribe.stomp11.listener import StompContext11
from django_stomp.services.subscribe.stomp11.listener import StompListener11
from django_stomp.settings.types import BrokerType
from django_stomp.settings.types import StompSettings

logger = logging.getLogger(__name__)


def pick_broker_adapter(settings: StompSettings):
    """
    Picks the appropriate broker adapter given some settings.
    """
    if settings.broker_type == BrokerType.RABBITMQ:
        return BrokerAdapterRabbitMQ(settings)

    if settings.broker_type == BrokerType.ACTIVEMQ:
        return BrokerAdapterRabbitMQ(settings)

    raise DjangoStompImproperlyConfigured(f"Can't find an adapter for broker type: {settings.broker_type}")


def create_listener_stomp11(
    subscription_callback: Callable, settings: StompSettings, param_to_callback: Optional[Any] = None
) -> StompListener11:
    """
    Builds a stomp listener for RabbitMQ broker.
    """
    broker_adapter = pick_broker_adapter(settings)
    stomp_context = StompContext11(settings, broker_adapter)
    wrapped_callback = subscription_callback_factory(
        stomp_context, subscription_callback, param_to_callback, settings.subscription.is_correlation_id_required
    )

    return StompListener11(wrapped_callback, stomp_context)
