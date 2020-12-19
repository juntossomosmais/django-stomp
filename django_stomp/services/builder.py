"""
Builder service for easily creating listeners and publishers.
"""

import logging
from typing import Callable

from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import only_destination_name
from django_stomp.infra.base_listener import ListenerRabbitMQ
from django_stomp.services.settings_scanner import DjangoStompSettings
from django_stomp.settings import build_connection_headers_rabbitmq
from django_stomp.settings import build_subscription_headers_rabbitmq
from django_stomp.settings import parse_stomp_connection_settings
from django_stomp.settings import parse_stomp_connection_settings_details
from django_stomp.settings import parse_subscription_settings

logger = logging.getLogger(__name__)


def create_listener_rabbitmq(
    callback: Callable, destination_name: str, settings: DjangoStompSettings
) -> ListenerRabbitMQ:
    """
    Builds a stomp listener for RabbitMQ broker.
    """
    # rabbitmq settings
    x_dead_letter_routing_key = create_dlq_destination_from_another_destination(destination_name)
    x_dead_letter_exchange = ""
    x_queue_name = only_destination_name(destination_name)
    auto_delete = False
    durable = True

    # rabbitmq headers
    stomp_connection_headers_rabbitmq = build_connection_headers_rabbitmq(
        x_dead_letter_routing_key, x_dead_letter_exchange
    )
    subscription_headers_rabbitmq = build_subscription_headers_rabbitmq(x_queue_name, auto_delete, durable)

    # stomp settings
    stomp_connection_settings = parse_stomp_connection_settings(settings)
    stomp_connection_settings_details = parse_stomp_connection_settings_details(
        settings, stomp_connection_headers_rabbitmq
    )
    stomp_subscription_settings = parse_subscription_settings(
        settings.listener_client_id,
        settings.subscription_id,
        settings.ack_type,
        destination_name,
        subscription_headers_rabbitmq,
    )

    return ListenerRabbitMQ(
        callback, stomp_connection_settings, stomp_connection_settings_details, stomp_subscription_settings,
    )
