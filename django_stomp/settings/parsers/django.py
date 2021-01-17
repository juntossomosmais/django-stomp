"""
Parser which reads Django stom settings from Django projects (Django conf object).
"""

import uuid
from typing import Optional

from django.conf import LazySettings

from django_stomp.helpers import build_final_client_id
from django_stomp.helpers import parse_ack_type
from django_stomp.helpers import parse_broker_type
from django_stomp.helpers import parse_stomp_protocol_version
from django_stomp.settings.defaults import STOMP_CORRELATION_ID_REQUIRED_DEFAULT
from django_stomp.settings.defaults import STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
from django_stomp.settings.defaults import STOMP_INCOMING_HEARTBEAT_DEFAULT
from django_stomp.settings.defaults import STOMP_LISTENER_CLIENT_ID_DEFAULT
from django_stomp.settings.defaults import STOMP_OUTGOING_HEARTBEAT_DEFAULT
from django_stomp.settings.defaults import STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
from django_stomp.settings.defaults import STOMP_PROTOCOL_VERSION_DEFAULT
from django_stomp.settings.defaults import STOMP_PUBLISHER_NAME_DEFAULT
from django_stomp.settings.defaults import STOMP_SSL_VERSION_DEFAULT
from django_stomp.settings.defaults import STOMP_USE_SSL_DEFAULT
from django_stomp.settings.parsers.support import get_config_as_bool_or_default
from django_stomp.settings.parsers.support import get_config_or_default
from django_stomp.settings.parsers.support import get_config_or_exception
from django_stomp.settings.types import AcknowledgementType
from django_stomp.settings.types import BrokerType
from django_stomp.settings.types import StompConnectionSettings
from django_stomp.settings.types import StompProtocolVersion
from django_stomp.settings.types import StompSettings
from django_stomp.settings.types import StompSubscriptionSettings


def parse_settings(destination: str, django_settings: LazySettings) -> StompSettings:
    """
    Parses project settings from Django as the config provider.
    """
    durable_topic_subscription: bool = get_config_or_default(
        django_settings, "STOMP_DURABLE_TOPIC_SUBSCRIPTION", STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
    )

    listener_client_id: Optional[str] = get_config_or_default(
        django_settings, "STOMP_LISTENER_CLIENT_ID", STOMP_LISTENER_CLIENT_ID_DEFAULT
    )
    final_listener_client_id: str = build_final_client_id(listener_client_id, durable_topic_subscription)

    is_correlation_id_required: bool = get_config_or_default(
        django_settings, "STOMP_CORRELATION_ID_REQUIRED", STOMP_CORRELATION_ID_REQUIRED_DEFAULT
    )

    process_msg_background: bool = get_config_or_default(
        django_settings, "STOMP_PROCESS_MSG_ON_BACKGROUND", STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
    )

    default_publisher_name: str = get_config_or_default(
        django_settings, "STOMP_PUBLISHER_NAME_DEFAULT", STOMP_PUBLISHER_NAME_DEFAULT
    )

    broker_type: BrokerType = parse_broker_type(get_config_or_default(django_settings, "STOMP_BROKER_TYPE", "rabbitmq"))
    ack_type: AcknowledgementType = parse_ack_type(get_config_or_default(django_settings, "STOMP_ACK_TYPE", "client"))

    # connection settings
    stomp_server_user: str = get_config_or_exception(django_settings, "STOMP_SERVER_USER")
    stomp_server_password: str = get_config_or_exception(django_settings, "STOMP_SERVER_PASSWORD")
    stomp_hosts_and_ports = [
        (
            get_config_or_exception(django_settings, "STOMP_SERVER_HOST"),
            int(get_config_or_exception(django_settings, "STOMP_SERVER_PORT")),
        )
    ]

    if get_config_or_default(django_settings, "STOMP_SERVER_STANDBY_HOST", None):
        stomp_hosts_and_ports_standby = (
            get_config_or_exception(django_settings, "STOMP_SERVER_STANDBY_HOST"),
            int(get_config_or_exception(django_settings, "STOMP_SERVER_STANDBY_PORT")),
        )
        stomp_hosts_and_ports.append(stomp_hosts_and_ports_standby)

    heartbeats = (
        get_config_or_default(django_settings, "STOMP_OUTGOING_HEARTBEAT", STOMP_OUTGOING_HEARTBEAT_DEFAULT),
        get_config_or_default(django_settings, "STOMP_INCOMING_HEARTBEAT", STOMP_INCOMING_HEARTBEAT_DEFAULT),
    )

    stomp_subscription_headers = get_config_or_default(django_settings, "STOMP_SUBSCRIPTION_HEADERS", {})
    stomp_connection_headers = get_config_or_default(django_settings, "STOMP_CONNECTION_HEADERS", {})

    # subscription settings
    subscription_id: str = get_config_or_default(django_settings, "STOMP_SUBSCRIPTION_ID", str(uuid.uuid4()))
    server_vhost: str = get_config_or_default(django_settings, "STOMP_SERVER_VHOST", None)

    use_ssl: bool = get_config_as_bool_or_default(django_settings, "STOMP_USE_SSL", STOMP_USE_SSL_DEFAULT)
    ssl_version: int = int(get_config_or_default(django_settings, "STOMP_SSL_VERSION", STOMP_SSL_VERSION_DEFAULT))

    stomp_protocol_version: StompProtocolVersion = parse_stomp_protocol_version(
        get_config_or_default(django_settings, "STOMP_SSL_VERSION", STOMP_PROTOCOL_VERSION_DEFAULT)
    )

    busy_wait_sleep_amount = 1  # sleep time on each iteration that sustains the main thread

    connection_settings = StompConnectionSettings(
        stomp_hosts_and_ports,
        use_ssl,
        ssl_version,
        heartbeats,
        server_vhost,
        final_listener_client_id,
        stomp_protocol_version,
        stomp_server_user,
        stomp_server_password,
        False,
        stomp_connection_headers,
    )

    subscription_settings = StompSubscriptionSettings(
        destination,
        subscription_id,
        ack_type,
        process_msg_background,
        durable_topic_subscription,
        is_correlation_id_required,
        default_publisher_name,
        busy_wait_sleep_amount,
        stomp_subscription_headers,
    )

    return StompSettings(broker_type, connection_settings, subscription_settings)
