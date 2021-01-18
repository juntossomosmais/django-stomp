"""
Parser which reads Django stom settings from Django projects (Django conf object).
"""

import uuid
from distutils.util import strtobool
from typing import Any
from typing import Optional

from django.conf import LazySettings

from django_stomp.exceptions import DjangoStompImproperlyConfigured
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
from django_stomp.settings.types import AcknowledgementType
from django_stomp.settings.types import BrokerType
from django_stomp.settings.types import StompConnectionSettings
from django_stomp.settings.types import StompProtocolVersion
from django_stomp.settings.types import StompSettings
from django_stomp.settings.types import StompSubscriptionSettings


def _get_config_or_default(django_config, env_name, default_value) -> Any:
    """
    Gets an env variable or returns a default value.
    """
    env_value = getattr(django_config, env_name, None)

    if env_value is None:
        return default_value

    return env_value


def _get_config_or_exception(django_config, env_name) -> Any:
    """
    Gets an env variable or raises an exception.
    """
    env_value = getattr(django_config, env_name, None)

    if env_value is None:
        raise DjangoStompImproperlyConfigured("Missing required env var is missing: %s", env_name)

    return env_value


def _get_config_as_bool_or_default(django_config, env_name, default_value) -> bool:
    """
    Evals env var strings as booleans.
    """
    env_var = _get_config_or_default(django_config, env_name, default_value)

    return bool(strtobool(env_var))


def parse_settings(destination: str, django_settings: LazySettings) -> StompSettings:
    """
    Parses project settings from Django as the config provider.
    """
    durable_topic_subscription: bool = _get_config_or_default(
        django_settings, "STOMP_DURABLE_TOPIC_SUBSCRIPTION", STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
    )

    listener_client_id: Optional[str] = _get_config_or_default(
        django_settings, "STOMP_LISTENER_CLIENT_ID", STOMP_LISTENER_CLIENT_ID_DEFAULT
    )
    final_listener_client_id: str = build_final_client_id(listener_client_id, durable_topic_subscription)

    is_correlation_id_required: bool = _get_config_or_default(
        django_settings, "STOMP_CORRELATION_ID_REQUIRED", STOMP_CORRELATION_ID_REQUIRED_DEFAULT
    )

    process_msg_background: bool = _get_config_or_default(
        django_settings, "STOMP_PROCESS_MSG_ON_BACKGROUND", STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
    )

    default_publisher_name: str = _get_config_or_default(
        django_settings, "STOMP_PUBLISHER_NAME_DEFAULT", STOMP_PUBLISHER_NAME_DEFAULT
    )

    broker_type: BrokerType = parse_broker_type(
        _get_config_or_default(django_settings, "STOMP_BROKER_TYPE", "rabbitmq")
    )
    ack_type: AcknowledgementType = parse_ack_type(_get_config_or_default(django_settings, "STOMP_ACK_TYPE", "client"))

    # connection settings
    stomp_server_user: str = _get_config_or_exception(django_settings, "STOMP_SERVER_USER")
    stomp_server_password: str = _get_config_or_exception(django_settings, "STOMP_SERVER_PASSWORD")
    stomp_hosts_and_ports = [
        (
            _get_config_or_exception(django_settings, "STOMP_SERVER_HOST"),
            int(_get_config_or_exception(django_settings, "STOMP_SERVER_PORT")),
        )
    ]

    if _get_config_or_default(django_settings, "STOMP_SERVER_STANDBY_HOST", None):
        stomp_hosts_and_ports_standby = (
            _get_config_or_exception(django_settings, "STOMP_SERVER_STANDBY_HOST"),
            int(_get_config_or_exception(django_settings, "STOMP_SERVER_STANDBY_PORT")),
        )
        stomp_hosts_and_ports.append(stomp_hosts_and_ports_standby)

    heartbeats = (
        _get_config_or_default(django_settings, "STOMP_OUTGOING_HEARTBEAT", STOMP_OUTGOING_HEARTBEAT_DEFAULT),
        _get_config_or_default(django_settings, "STOMP_INCOMING_HEARTBEAT", STOMP_INCOMING_HEARTBEAT_DEFAULT),
    )

    stomp_subscription_headers = _get_config_or_default(django_settings, "STOMP_SUBSCRIPTION_HEADERS", {})
    stomp_connection_headers = _get_config_or_default(django_settings, "STOMP_CONNECTION_HEADERS", {})

    # subscription settings
    subscription_id: str = _get_config_or_default(django_settings, "STOMP_SUBSCRIPTION_ID", str(uuid.uuid4()))
    server_vhost: str = _get_config_or_default(django_settings, "STOMP_SERVER_VHOST", None)

    use_ssl: bool = _get_config_as_bool_or_default(django_settings, "STOMP_USE_SSL", STOMP_USE_SSL_DEFAULT)
    ssl_version: int = int(_get_config_or_default(django_settings, "STOMP_SSL_VERSION", STOMP_SSL_VERSION_DEFAULT))

    stomp_protocol_version: StompProtocolVersion = parse_stomp_protocol_version(
        _get_config_or_default(django_settings, "STOMP_SSL_VERSION", STOMP_PROTOCOL_VERSION_DEFAULT)
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
