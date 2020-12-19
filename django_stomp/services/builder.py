"""
Builder service for easily creating listeners and publishers.
"""

import logging
from typing import Callable

from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import only_destination_name
from django_stomp.infra.base_listener import BaseStompListener
from django_stomp.infra.base_listener import ListenerRabbitMQ
from django_stomp.infra.base_listener import build_connection_headers_rabbitmq
from django_stomp.infra.base_listener import build_stomp_connect_frame_settings
from django_stomp.infra.base_listener import build_stomp_connection_settings
from django_stomp.infra.base_listener import build_subscription_details_rabbitmq
from django_stomp.services.settings_scanner import DjangoStompSettings

logger = logging.getLogger(__name__)


def create_listener_rabbitmq(
    callback: Callable, destination_name: str, settings: DjangoStompSettings
) -> BaseStompListener:
    """
    Builds a stomp listener for RabbitMQ broker.
    """
    x_dead_letter_routing_key = create_dlq_destination_from_another_destination(destination_name)
    x_dead_letter_exchange = ""
    x_queue_name = only_destination_name(destination_name)
    auto_delete = False
    durable = True

    stomp_connection_settings = build_stomp_connection_settings(settings)
    stomp_connection_headers_rabbitmq = build_connection_headers_rabbitmq(
        x_dead_letter_routing_key, x_dead_letter_exchange
    )
    stomp_connect_frame_settings = build_stomp_connect_frame_settings(stomp_connection_headers_rabbitmq, settings)
    stomp_subscription_details = build_subscription_details_rabbitmq(
        settings.ack_type.value, destination_name, x_queue_name, auto_delete, durable
    )

    return ListenerRabbitMQ(
        callback,
        stomp_connection_settings,
        stomp_connect_frame_settings,
        stomp_subscription_details,
        settings.client_id,
        settings.subscription_id,
    )
