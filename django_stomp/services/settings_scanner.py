"""
Service used to read user settings.
"""
from dataclasses import dataclass
from typing import Optional


from django_stomp.infra.env import get_config_as_bool_or_default, get_config_or_default, get_config_or_default_any
from django_stomp.infra.env import get_config_or_exception
from django_stomp.settings import (
    STOMP_CORRELATION_ID_REQUIRED_DEFAULT,
    STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT,
    STOMP_INCOMING_HEARTBEAT_DEFAULT,
    STOMP_LISTENER_CLIENT_ID_DEFAULT,
    STOMP_OUTGOING_HEARTBEAT_DEFAULT,
    STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT,
    STOMP_SSL_VERSION_DEFAULT,
    STOMP_USE_SSL_DEFAULT,
    STOMP_WAIT_TO_CONNECT_DEFAULT,
)

from django.conf import LazySettings


@dataclass(frozen=True)
class DjangoStompSettings:
    """
    Django stomp settings.
    """

    listener_client_id: Optional[str]
    publisher_name: str
    durable_topic_subscription: bool
    is_correlation_id_required: bool
    should_process_msg_on_background: bool

    stomp_server_user: str
    stomp_server_password: str
    stomp_server_host: str
    stomp_server_port: int
    stomp_server_standby_host: str
    stomp_server_standby_port: int
    wait_to_connect: int
    outgoing_heartbeat: int
    incoming_heartbeat: int
    subscription_id: Optional[str]
    vhost: str
    use_ssl: bool
    ssl_version: int


def scan_django_settings(django_settings: LazySettings) -> DjangoStompSettings:
    """
    Reads all required settings from users' django settings.
    """

    # operation settings
    durable_topic_subscription = get_config_as_bool_or_default(
        "STOMP_DURABLE_TOPIC_SUBSCRIPTION", STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
    )
    listener_client_id = get_config_or_default_any("STOMP_LISTENER_CLIENT_ID", STOMP_LISTENER_CLIENT_ID_DEFAULT)
    is_correlation_id_required = get_config_as_bool_or_default(
        "STOMP_CORRELATION_ID_REQUIRED", STOMP_CORRELATION_ID_REQUIRED_DEFAULT
    )
    should_process_msg_on_background = get_config_as_bool_or_default(
        "STOMP_PROCESS_MSG_ON_BACKGROUND", STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
    )
    default_publisher_name = get_config_or_default("STOMP_PUBLISHER_NAME_DEFAULT", "django-stomp-another-target")

    # connection settings
    stomp_server_user = get_config_or_exception("STOMP_SERVER_USER")
    stomp_server_password = get_config_or_exception("STOMP_SERVER_PASSWORD")

    stomp_server_host = get_config_or_exception("STOMP_SERVER_HOST")
    stomp_server_port = int(get_config_or_exception("STOMP_SERVER_PORT"))

    stomp_server_standby_host: str = get_config_or_default_any("STOMP_SERVER_STANDBY_HOST", None)
    stomp_server_standby_port = int(get_config_or_exception("STOMP_SERVER_STANDBY_PORT"))

    wait_to_connect = int(get_config_or_default("STOMP_WAIT_TO_CONNECT", STOMP_WAIT_TO_CONNECT_DEFAULT))
    outgoing_heartbeat = int(get_config_or_default("STOMP_OUTGOING_HEARTBEAT", STOMP_OUTGOING_HEARTBEAT_DEFAULT))
    incoming_heartbeat = int(get_config_or_default("STOMP_INCOMING_HEARTBEAT", STOMP_INCOMING_HEARTBEAT_DEFAULT))

    # TODO: review client_id
    subscription_id: Optional[str] = get_config_or_default_any("STOMP_SUBSCRIPTION_ID", None)
    vhost = get_config_or_default_any("STOMP_SERVER_VHOST", None)

    use_ssl = get_config_as_bool_or_default("STOMP_USE_SSL", STOMP_USE_SSL_DEFAULT)
    ssl_version = int(get_config_or_default("STOMP_SSL_VERSION", STOMP_SSL_VERSION_DEFAULT))

    return DjangoStompSettings(
        wait_to_connect=wait_to_connect,
        durable_topic_subscription=durable_topic_subscription,
        listener_client_id=listener_client_id,
        is_correlation_id_required=is_correlation_id_required,
        should_process_msg_on_background=should_process_msg_on_background,
        publisher_name=default_publisher_name,
        stomp_server_host=stomp_server_host,
        stomp_server_user=stomp_server_user,
        stomp_server_password=stomp_server_password,
        stomp_server_port=stomp_server_port,
        stomp_server_standby_host=stomp_server_standby_host,
        stomp_server_standby_port=stomp_server_standby_port,
        outgoing_heartbeat=outgoing_heartbeat,
        incoming_heartbeat=incoming_heartbeat,
        subscription_id=subscription_id,
        vhost=vhost,
        use_ssl=use_ssl,
        ssl_version=ssl_version,
    )
