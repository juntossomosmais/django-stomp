import logging
import ssl
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any
from typing import Callable
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from django.conf import settings as django_settings
from typing_extensions import TypedDict

from django_stomp.exceptions import DjangoStompImproperlyConfigured
from django_stomp.helpers import build_final_client_id
from django_stomp.helpers import display_heartbeat_warning_if_necessary
from django_stomp.helpers import eval_as_int_if_provided_value_is_not_none_otherwise_none
from django_stomp.infra.env import get_config_as_bool_or_default
from django_stomp.infra.env import get_config_or_default
from django_stomp.infra.env import get_config_or_default_any
from django_stomp.infra.env import get_config_or_exception

logger = logging.getLogger(__name__)


def eval_settings_otherwise_raise_exception(
    settings_name: str, evaluation_callback: Callable, default_value: Optional[Any] = None
):
    try:
        return evaluation_callback(getattr(django_settings, settings_name, default_value))
    except Exception:
        raise DjangoStompImproperlyConfigured(f"The defined {settings_name} is not valid!")


STOMP_PROCESS_MSG_WORKERS = eval_settings_otherwise_raise_exception(
    "STOMP_PROCESS_MSG_WORKERS", eval_as_int_if_provided_value_is_not_none_otherwise_none
)

# stomp default settings
STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT = "False"
STOMP_LISTENER_CLIENT_ID_DEFAULT = None
STOMP_CORRELATION_ID_REQUIRED_DEFAULT = "True"
STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT = "True"
STOMP_PUBLISHER_NAME_DEFAULT = "django-stomp-another-target"

# connection default settings
STOMP_WAIT_TO_CONNECT_DEFAULT = "10"
STOMP_OUTGOING_HEARTBEAT_DEFAULT = "10000"
STOMP_INCOMING_HEARTBEAT_DEFAULT = "10000"
STOMP_USE_SSL_DEFAULT = "False"
STOMP_SSL_VERSION_DEFAULT = str(ssl.PROTOCOL_TLS)


class AcknowledgementType(Enum):
    """
    Ack types.
    """

    CLIENT: str = "client"
    CLIENT_INDIVIDUAL: str = "client-individual"
    AUTO: str = "auto"


@dataclass(frozen=True)
class DjangoStompSettings:
    """
    Django stomp settings.
    """

    listener_client_id: str
    subscription_id: str
    publisher_name: str

    durable_topic_subscription: bool
    is_correlation_id_required: bool
    should_process_msg_on_background: bool
    ack_type: AcknowledgementType

    stomp_server_user: str
    stomp_server_password: str
    stomp_server_host: str
    stomp_server_port: int
    stomp_server_standby_host: str
    stomp_server_standby_port: int
    wait_to_connect: int
    outgoing_heartbeat: int
    incoming_heartbeat: int
    vhost: str
    use_ssl: bool
    ssl_version: int


# Headers must be typed dicts due to hyphened keys!
# ---- StompConnectionHeaders
ConnectionHeadersRabbitMQ = TypedDict(
    "ConnectionHeadersRabbitMQ",
    {"prefetch-count": str, "x-dead-letter-routing-key": str, "x-dead-letter-exchange": str},
)
ConnectionHeadersActiveMQ = TypedDict(
    "ConnectionHeadersActiveMQ",
    {
        "client-id": str,
        "activemq.prefetchSize": str,
        "activemq.subscriptionName": str,
        "activemq.subcriptionName": str,  # yes, it's like this
    },
)

# ---- StompSubscriptionHeaders
StompSubscriptionHeadersActiveMQ = TypedDict("StompSubscriptionHeadersActiveMQ", {})
StompSubscriptionHeadersRabbitMQ = TypedDict(
    "StompSubscriptionHeadersRabbitMQ", {"x-queue-name": str, "auto-delete": bool, "durable": bool},
)


@dataclass(frozen=True)
class StompConnectionSettings:
    hosts_and_ports: List[Tuple[str, int]]
    use_ssl: bool
    ssl_version: int
    heartbeats: Tuple[int, int]
    vhost: str


# def connect(self, username=None, passcode=None, wait=False, headers=None, **keyword_headers):@dataclass(frozen=True)
@dataclass(frozen=True)
class StompConnectionSettingsDetails:
    username: str
    passcode: str
    wait: bool
    headers: Union[ConnectionHeadersRabbitMQ, ConnectionHeadersActiveMQ]


# def subscribe(self, destination, id, ack="auto", headers=None, **keyword_headers):
@dataclass(frozen=True)
class StompSubscriptionSettings:
    destination: str
    listener_client_id: str
    subscription_id: str
    ack_type: AcknowledgementType
    headers: Union[StompSubscriptionHeadersRabbitMQ, StompSubscriptionHeadersActiveMQ]


def read_django_stomp_required_settings() -> DjangoStompSettings:
    """
    Reads all required settings from users' django settings.
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
        listener_client_id=listener_client_id,
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


def parse_stomp_connection_settings(settings: DjangoStompSettings) -> StompConnectionSettings:
    hosts_and_ports: List[Tuple[str, int]] = [(settings.stomp_server_host, settings.stomp_server_port)]

    if settings.stomp_server_standby_host and settings.stomp_server_standby_port:
        hosts_and_ports.append((settings.stomp_server_standby_host, settings.stomp_server_standby_port))

    logger.info(
        f"Use SSL? {settings.use_ssl}. Version: {settings.ssl_version}. Outgoing/Ingoing heartbeat: "
        f"{settings.outgoing_heartbeat}/{settings.incoming_heartbeat}. "
        f"Background? {settings.should_process_msg_on_background}"
    )

    display_heartbeat_warning_if_necessary(settings)

    return StompConnectionSettings(
        hosts_and_ports=hosts_and_ports,
        use_ssl=settings.use_ssl,
        ssl_version=settings.ssl_version,
        heartbeats=(settings.outgoing_heartbeat, settings.incoming_heartbeat),
        vhost=settings.vhost,
    )


def parse_stomp_connection_settings_details(
    settings: DjangoStompSettings, connection_headers: Union[ConnectionHeadersRabbitMQ, ConnectionHeadersActiveMQ]
) -> StompConnectionSettingsDetails:
    return StompConnectionSettingsDetails(
        username=settings.stomp_server_user,
        passcode=settings.stomp_server_password,
        wait=True,
        headers=connection_headers,
    )


def parse_subscription_settings(
    listener_client_id: str,
    subscription_id: str,
    ack_type: AcknowledgementType,
    destination: str,
    headers: Union[StompSubscriptionHeadersRabbitMQ, StompSubscriptionHeadersActiveMQ],
) -> StompSubscriptionSettings:
    return StompSubscriptionSettings(
        listener_client_id=listener_client_id,
        subscription_id=subscription_id,
        ack_type=ack_type,
        destination=destination,
        headers=headers,
    )


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
