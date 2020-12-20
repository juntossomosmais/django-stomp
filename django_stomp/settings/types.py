"""
Type definitions related to django-stomp's configuration.

Headers must be typed dicts due to hyphened keys!
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List
from typing import Tuple
from typing import Union

from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


class AcknowledgementType(Enum):
    """
    Ack types.
    """

    CLIENT: str = "client"
    CLIENT_INDIVIDUAL: str = "client-individual"
    AUTO: str = "auto"


class BrokerType(Enum):
    """
    Supported broker types.
    """

    RABBITMQ: str = "rabbitmq"
    ACTIVEMQ: str = "activemq"


# Subscription Headers
StompSubscriptionHeadersActiveMQ = TypedDict("StompSubscriptionHeadersActiveMQ", {})
StompSubscriptionHeadersRabbitMQ = TypedDict(
    "StompSubscriptionHeadersRabbitMQ", {"x-queue-name": str, "auto-delete": bool, "durable": bool},
)
# Connection Headers
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


@dataclass(frozen=True)
class StompConnectionSettings:
    """
    Connection-related settings for django-stomp.
    """

    hosts_and_ports: List[Tuple[str, int]]
    use_ssl: bool
    ssl_version: int
    heartbeats: Tuple[int, int]
    vhost: str

    # credentials and headers
    username: str
    passcode: str
    wait: bool
    headers: Union[ConnectionHeadersRabbitMQ, ConnectionHeadersActiveMQ]
    should_process_msg_on_background: bool


@dataclass(frozen=True)
class StompSubscriptionSettings:
    """
    Subscription-related settings for django-stomp.
    """

    destination: str
    listener_client_id: str
    subscription_id: str
    ack_type: AcknowledgementType
    headers: Union[StompSubscriptionHeadersRabbitMQ, StompSubscriptionHeadersActiveMQ]

    durable_topic_subscription: bool
    is_correlation_id_required: bool
    publisher_broker_mover_name: str  # TODO: review later


@dataclass(frozen=True)
class DjangoStompSettings:
    """
    All settings required to run django-stomp.
    """

    broker_type: BrokerType
    connection_settings: StompConnectionSettings
    subscription_settings: StompSubscriptionSettings
