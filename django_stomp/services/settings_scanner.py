"""
Service used to read user settings.
"""
import uuid

from django_stomp.helpers import build_final_client_id
from django_stomp.infra.env import get_config_as_bool_or_default
from django_stomp.infra.env import get_config_or_default
from django_stomp.infra.env import get_config_or_default_any
from django_stomp.infra.env import get_config_or_exception
from django_stomp.settings import STOMP_CORRELATION_ID_REQUIRED_DEFAULT
from django_stomp.settings import STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
from django_stomp.settings import STOMP_INCOMING_HEARTBEAT_DEFAULT
from django_stomp.settings import STOMP_LISTENER_CLIENT_ID_DEFAULT
from django_stomp.settings import STOMP_OUTGOING_HEARTBEAT_DEFAULT
from django_stomp.settings import STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
from django_stomp.settings import STOMP_SSL_VERSION_DEFAULT
from django_stomp.settings import STOMP_USE_SSL_DEFAULT
from django_stomp.settings import STOMP_WAIT_TO_CONNECT_DEFAULT
from django_stomp.settings import AcknowledgementType
from django_stomp.settings import DjangoStompSettings


def scan_django_settings() -> DjangoStompSettings:
    """
    Reads all required settings from users' django settings.
    """

    # operation settings
    durable_topic_subscription = get_config_as_bool_or_default(
        "STOMP_DURABLE_TOPIC_SUBSCRIPTION", STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
    )
    listener_client_id = get_config_or_default_any("STOMP_LISTENER_CLIENT_ID", STOMP_LISTENER_CLIENT_ID_DEFAULT)
    client_id = build_final_client_id(listener_client_id, durable_topic_subscription)  # this one goes ahead

    is_correlation_id_required = get_config_as_bool_or_default(
        "STOMP_CORRELATION_ID_REQUIRED", STOMP_CORRELATION_ID_REQUIRED_DEFAULT
    )
    should_process_msg_on_background = get_config_as_bool_or_default(
        "STOMP_PROCESS_MSG_ON_BACKGROUND", STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
    )
    default_publisher_name = get_config_or_default("STOMP_PUBLISHER_NAME_DEFAULT", "django-stomp-another-target")

    ack_type = AcknowledgementType.CLIENT

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
    subscription_id: str = get_config_or_default("STOMP_SUBSCRIPTION_ID", str(uuid.uuid4()))
    vhost = get_config_or_default_any("STOMP_SERVER_VHOST", None)

    use_ssl = get_config_as_bool_or_default("STOMP_USE_SSL", STOMP_USE_SSL_DEFAULT)
    ssl_version = int(get_config_or_default("STOMP_SSL_VERSION", STOMP_SSL_VERSION_DEFAULT))

    return DjangoStompSettings(
        wait_to_connect=wait_to_connect,
        durable_topic_subscription=durable_topic_subscription,
        client_id=client_id,
        is_correlation_id_required=is_correlation_id_required,
        should_process_msg_on_background=should_process_msg_on_background,
        ack_type=ack_type,
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
