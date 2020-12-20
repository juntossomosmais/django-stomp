"""
Module with functions required to read django-stomp's settings from django projects configuration.
"""

import logging
import uuid
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from django_stomp.exceptions import DjangoStompImproperlyConfigured
from django_stomp.helpers import build_final_client_id
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import only_destination_name
from django_stomp.settings.default_values import STOMP_CORRELATION_ID_REQUIRED_DEFAULT
from django_stomp.settings.default_values import STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
from django_stomp.settings.default_values import STOMP_INCOMING_HEARTBEAT_DEFAULT
from django_stomp.settings.default_values import STOMP_LISTENER_CLIENT_ID_DEFAULT
from django_stomp.settings.default_values import STOMP_OUTGOING_HEARTBEAT_DEFAULT
from django_stomp.settings.default_values import STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
from django_stomp.settings.default_values import STOMP_SSL_VERSION_DEFAULT
from django_stomp.settings.default_values import STOMP_USE_SSL_DEFAULT
from django_stomp.settings.django_stomp import DjangoStompSettings
from django_stomp.settings.django_stomp import StompConnectionSettings
from django_stomp.settings.django_stomp import StompSubscriptionSettings
from django_stomp.settings.support import get_config_as_bool_or_default
from django_stomp.settings.support import get_config_or_default
from django_stomp.settings.support import get_config_or_default_any
from django_stomp.settings.support import get_config_or_exception
from django_stomp.settings.types import AcknowledgementType
from django_stomp.settings.types import BrokerType
from django_stomp.settings.types import ConnectionHeadersActiveMQ
from django_stomp.settings.types import ConnectionHeadersRabbitMQ
from django_stomp.settings.types import StompSubscriptionHeadersActiveMQ
from django_stomp.settings.types import StompSubscriptionHeadersRabbitMQ

logger = logging.getLogger(__name__)


def build_django_stomp_settings(destination_name: str) -> DjangoStompSettings:
    """
    Extracts required configuration variables from the users's django projects.
    """

    # operation settings
    durable_topic_subscription = get_config_as_bool_or_default(
        "STOMP_DURABLE_TOPIC_SUBSCRIPTION", STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
    )
    listener_client_id = get_config_or_default_any("STOMP_LISTENER_CLIENT_ID", STOMP_LISTENER_CLIENT_ID_DEFAULT)
    listener_client_id = build_final_client_id(listener_client_id, durable_topic_subscription)  # this one goes ahead

    is_correlation_id_required = get_config_as_bool_or_default(
        "STOMP_CORRELATION_ID_REQUIRED", STOMP_CORRELATION_ID_REQUIRED_DEFAULT
    )
    should_process_msg_on_background = get_config_as_bool_or_default(
        "STOMP_PROCESS_MSG_ON_BACKGROUND", STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
    )
    default_publisher_name = get_config_or_default(
        "STOMP_PUBLISHER_NAME_DEFAULT", "django-stomp-another-target"
    )

    broker_type: BrokerType = get_config_or_default_any("STOMP_BROKER_TYPE", BrokerType.RABBITMQ)
    ack_type = AcknowledgementType.CLIENT

    # connection settings
    stomp_server_user = get_config_or_exception("STOMP_SERVER_USER")
    stomp_server_password = get_config_or_exception("STOMP_SERVER_PASSWORD")

    stomp_server_host = get_config_or_exception("STOMP_SERVER_HOST")
    stomp_server_port = int(get_config_or_exception("STOMP_SERVER_PORT"))

    stomp_server_standby_host: str = get_config_or_default_any("STOMP_SERVER_STANDBY_HOST", None)
    stomp_server_standby_port = get_config_or_default_any("STOMP_SERVER_STANDBY_PORT", None)

    if stomp_server_standby_port is not None:
        stomp_server_standby_port = int(stomp_server_standby_port)

    # wait_to_connect = int(get_config_or_default("STOMP_WAIT_TO_CONNECT", STOMP_WAIT_TO_CONNECT_DEFAULT))
    outgoing_heartbeat = int(get_config_or_default("STOMP_OUTGOING_HEARTBEAT", STOMP_OUTGOING_HEARTBEAT_DEFAULT))
    incoming_heartbeat = int(get_config_or_default("STOMP_INCOMING_HEARTBEAT", STOMP_INCOMING_HEARTBEAT_DEFAULT))

    # TODO: review client_id
    subscription_id: str = get_config_or_default("STOMP_SUBSCRIPTION_ID", str(uuid.uuid4()))
    vhost = get_config_or_default_any("STOMP_SERVER_VHOST", None)

    use_ssl = get_config_as_bool_or_default("STOMP_USE_SSL", STOMP_USE_SSL_DEFAULT)
    ssl_version = int(get_config_or_default("STOMP_SSL_VERSION", STOMP_SSL_VERSION_DEFAULT))

    if broker_type == BrokerType.RABBITMQ:
        x_dead_letter_routing_key = create_dlq_destination_from_another_destination(destination_name)
        x_dead_letter_exchange = ""
        x_queue_name = only_destination_name(destination_name)
        auto_delete = False
        durable = True

        connection_headers = build_connection_headers_rabbitmq(
            x_dead_letter_routing_key, x_dead_letter_exchange, prefetch_count=1
        )
        subscription_headers = build_subscription_headers_rabbitmq(x_queue_name, auto_delete, durable)

    else:
        raise DjangoStompImproperlyConfigured

    connection_settings = parse_stomp_connection_settings(
        stomp_server_host,
        stomp_server_port,
        outgoing_heartbeat,
        incoming_heartbeat,
        use_ssl,
        ssl_version,
        vhost,
        should_process_msg_on_background,
        stomp_server_user,
        stomp_server_password,
        True,
        connection_headers,
        stomp_server_standby_host,
        stomp_server_standby_port,
    )

    subscription_settings = parse_subscription_settings(
        listener_client_id,
        subscription_id,
        ack_type,
        destination_name,
        subscription_headers,
        durable_topic_subscription,
        is_correlation_id_required,
        default_publisher_name,
    )

    return DjangoStompSettings(broker_type, connection_settings, subscription_settings)


def build_connection_headers_rabbitmq(
    x_dead_letter_routing_key: str, x_dead_letter_exchange: str, prefetch_count: int = 1
) -> ConnectionHeadersRabbitMQ:
    return {
        "prefetch-count": str(prefetch_count),
        "x-dead-letter-routing-key": x_dead_letter_routing_key,
        "x-dead-letter-exchange": x_dead_letter_exchange,
    }


def build_subscription_headers_rabbitmq(
    x_queue_name: str, auto_delete: bool, durable: bool
) -> StompSubscriptionHeadersRabbitMQ:
    return {"x-queue-name": x_queue_name, "auto-delete": auto_delete, "durable": durable}


def parse_stomp_connection_settings(
    stomp_server_host: str,
    stomp_server_port: int,
    outgoing_heartbeat: int,
    incoming_heartbeat: int,
    use_ssl: bool,
    ssl_version: int,
    vhost: str,
    should_process_msg_on_background: bool,
    username: str,
    passcode: str,
    wait: bool,
    connection_headers: Union[ConnectionHeadersRabbitMQ, ConnectionHeadersActiveMQ],
    stomp_server_standby_host: Optional[str],
    stomp_server_standby_port: Optional[int],
) -> StompConnectionSettings:
    hosts_and_ports: List[Tuple[str, int]] = [(stomp_server_host, stomp_server_port)]

    if stomp_server_standby_host and stomp_server_standby_port:
        hosts_and_ports.append((stomp_server_standby_host, stomp_server_standby_port))

    logger.info(
        f"Use SSL? {use_ssl}. Version: {ssl_version}. Outgoing/Ingoing heartbeat: "
        f"{outgoing_heartbeat}/{incoming_heartbeat}. "
        f"Background? {should_process_msg_on_background}"
    )

    # display_heartbeat_warning_if_necessary(settings)

    return StompConnectionSettings(
        hosts_and_ports=hosts_and_ports,
        use_ssl=use_ssl,
        ssl_version=ssl_version,
        heartbeats=(outgoing_heartbeat, incoming_heartbeat),
        vhost=vhost,
        username=username,
        passcode=passcode,
        wait=wait,
        headers=connection_headers,
        should_process_msg_on_background=should_process_msg_on_background,
    )


def parse_subscription_settings(
    listener_client_id: str,
    subscription_id: str,
    ack_type: AcknowledgementType,
    destination: str,
    headers: Union[StompSubscriptionHeadersActiveMQ, StompSubscriptionHeadersActiveMQ],
    durable_topic_subscription: bool,
    is_correlation_id_required: bool,
    publisher_broker_mover_name: str = "publisher",
) -> StompSubscriptionSettings:
    return StompSubscriptionSettings(
        listener_client_id=listener_client_id,
        subscription_id=subscription_id,
        ack_type=ack_type,
        destination=destination,
        headers=headers,
        durable_topic_subscription=durable_topic_subscription,
        is_correlation_id_required=is_correlation_id_required,
        publisher_broker_mover_name=publisher_broker_mover_name,
    )
