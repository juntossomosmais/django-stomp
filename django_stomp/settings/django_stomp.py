"""
Module with functions required to read django-stomp's settings from django projects configuration.
"""

import logging
from typing import List
from typing import Tuple
from typing import Union

from django_stomp.exceptions import DjangoStompImproperlyConfigured
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import only_destination_name
from django_stomp.settings.django_project import ACK_TYPE
from django_stomp.settings.django_project import BROKER_TYPE
from django_stomp.settings.django_project import DEFAULT_PUBLISHER_NAME
from django_stomp.settings.django_project import DURABLE_TOPIC_SUBSCRIPTION
from django_stomp.settings.django_project import INCOMING_HEARTBEAT
from django_stomp.settings.django_project import IS_CORRELATION_ID_REQUIRED
from django_stomp.settings.django_project import LISTENER_CLIENT_ID
from django_stomp.settings.django_project import OUTGOING_HEARTBEAT
from django_stomp.settings.django_project import SERVER_VHOST
from django_stomp.settings.django_project import SHOULD_PROCESS_MSG_ON_BACKGROUND
from django_stomp.settings.django_project import SSL_VERSION
from django_stomp.settings.django_project import STOMP_SERVER_HOST
from django_stomp.settings.django_project import STOMP_SERVER_PASSWORD
from django_stomp.settings.django_project import STOMP_SERVER_PORT
from django_stomp.settings.django_project import STOMP_SERVER_STANDBY_HOST
from django_stomp.settings.django_project import STOMP_SERVER_STANDBY_PORT
from django_stomp.settings.django_project import STOMP_SERVER_USER
from django_stomp.settings.django_project import SUBSCRIPTION_ID
from django_stomp.settings.django_project import USE_SSL
from django_stomp.settings.types import BrokerType
from django_stomp.settings.types import ConnectionHeadersActiveMQ
from django_stomp.settings.types import ConnectionHeadersRabbitMQ
from django_stomp.settings.types import DjangoStompSettings
from django_stomp.settings.types import StompConnectionSettings
from django_stomp.settings.types import StompSubscriptionHeadersActiveMQ
from django_stomp.settings.types import StompSubscriptionHeadersRabbitMQ
from django_stomp.settings.types import StompSubscriptionSettings

logger = logging.getLogger(__name__)


def _build_connection_headers_activemq(listener_client_id: str, prefetch_size: int = 1) -> ConnectionHeadersActiveMQ:
    return {
        "client-id": listener_client_id,
        "activemq.prefetchSize": str(prefetch_size),
        "activemq.subscriptionName": f"{listener_client_id}-listener",
        "activemq.subcriptionName": f"{listener_client_id}-listener",  # yes, it's like this
    }


def _build_subscription_headers_activemq() -> StompSubscriptionHeadersActiveMQ:
    return {}  # none so far


def _build_connection_headers_rabbitmq(
    x_dead_letter_routing_key: str, x_dead_letter_exchange: str, prefetch_count: int = 1
) -> ConnectionHeadersRabbitMQ:
    return {
        "prefetch-count": str(prefetch_count),
        "x-dead-letter-routing-key": x_dead_letter_routing_key,
        "x-dead-letter-exchange": x_dead_letter_exchange,
    }


def _build_subscription_headers_rabbitmq(
    x_queue_name: str, auto_delete: bool, durable: bool
) -> StompSubscriptionHeadersRabbitMQ:
    return {"x-queue-name": x_queue_name, "auto-delete": auto_delete, "durable": durable}


def _compile_stomp_connection_settings(
    connection_headers: Union[ConnectionHeadersRabbitMQ, ConnectionHeadersActiveMQ],
) -> StompConnectionSettings:
    hosts_and_ports: List[Tuple[str, int]] = [(STOMP_SERVER_HOST, STOMP_SERVER_PORT)]

    if STOMP_SERVER_STANDBY_HOST and STOMP_SERVER_STANDBY_PORT:
        hosts_and_ports.append((STOMP_SERVER_STANDBY_HOST, STOMP_SERVER_STANDBY_PORT))

    logger.info(
        f"Use SSL? {USE_SSL}. Version: {SSL_VERSION}. Outgoing/Ingoing heartbeat: "
        f"{OUTGOING_HEARTBEAT}/{INCOMING_HEARTBEAT}. "
        f"Background? {SHOULD_PROCESS_MSG_ON_BACKGROUND}"
    )

    # display_heartbeat_warning_if_necessary(settings)

    return StompConnectionSettings(
        hosts_and_ports=hosts_and_ports,
        use_ssl=USE_SSL,
        ssl_version=SSL_VERSION,
        heartbeats=(OUTGOING_HEARTBEAT, INCOMING_HEARTBEAT),
        vhost=SERVER_VHOST,
        username=STOMP_SERVER_USER,
        passcode=STOMP_SERVER_PASSWORD,
        wait=True,
        headers=connection_headers,
        should_process_msg_on_background=SHOULD_PROCESS_MSG_ON_BACKGROUND,
    )


def _compile_subscription_settings(
    destination: str, subscription_headers: Union[StompSubscriptionHeadersActiveMQ, StompSubscriptionHeadersActiveMQ],
) -> StompSubscriptionSettings:
    return StompSubscriptionSettings(
        listener_client_id=LISTENER_CLIENT_ID,
        subscription_id=SUBSCRIPTION_ID,
        ack_type=ACK_TYPE,
        destination=destination,
        headers=subscription_headers,
        durable_topic_subscription=DURABLE_TOPIC_SUBSCRIPTION,
        is_correlation_id_required=IS_CORRELATION_ID_REQUIRED,
        publisher_broker_mover_name=DEFAULT_PUBLISHER_NAME,
    )


def compile_django_stomp_settings(destination_name: str) -> DjangoStompSettings:
    """
    Compiles all required django stomp settings into a single useful data type: DjangoStompSettings.
    """
    connection_headers: Union[ConnectionHeadersRabbitMQ, ConnectionHeadersActiveMQ]
    subscription_headers: Union[StompSubscriptionHeadersRabbitMQ, StompSubscriptionHeadersActiveMQ]

    if BROKER_TYPE == BrokerType.RABBITMQ:
        x_dead_letter_routing_key = create_dlq_destination_from_another_destination(destination_name)
        x_dead_letter_exchange = ""
        x_queue_name = only_destination_name(destination_name)
        auto_delete = False
        durable = True

        connection_headers = _build_connection_headers_rabbitmq(
            x_dead_letter_routing_key, x_dead_letter_exchange, prefetch_count=1
        )
        subscription_headers = _build_subscription_headers_rabbitmq(x_queue_name, auto_delete, durable)
    elif BROKER_TYPE == BrokerType.ACTIVEMQ:
        connection_headers = _build_connection_headers_activemq(LISTENER_CLIENT_ID, prefetch_size=1)
        subscription_headers = _build_subscription_headers_activemq()
    else:
        raise DjangoStompImproperlyConfigured(f"Unsupported broker vendor: {BROKER_TYPE}!")

    connection_settings = _compile_stomp_connection_settings(connection_headers)
    subscription_settings = _compile_subscription_settings(destination_name, subscription_headers)

    return DjangoStompSettings(BROKER_TYPE, connection_settings, subscription_settings)
