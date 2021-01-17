"""
Type definitions related to django-stomp's configuration.

Headers must be typed dicts due to hyphened keys!
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

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


class StompProtocolVersion(Enum):
    """
    Supported STOMP versions.
    """

    VERSION_10: str = "1.0"
    VERSION_11: str = "1.1"
    VERSION_12: str = "1.2"


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
    listener_client_id: str
    stomp_protocol_version: StompProtocolVersion

    # credentials and headers
    username: Optional[str]
    passcode: Optional[str]
    wait: bool

    # extra custom setup
    extra_headers: Dict


@dataclass(frozen=True)
class StompSubscriptionSettings:
    """
    Subscription-related settings for django-stomp.
    """

    destination: str
    subscription_id: str
    ack_type: AcknowledgementType
    process_msg_background: bool

    durable_topic_subscription: bool
    is_correlation_id_required: bool
    publisher_broker_mover_name: str  # TODO: review later

    # extra setup
    busy_wait_sleep_amount: int
    extra_headers: Dict


@dataclass(frozen=True)
class StompSettings:
    """
    All required settings.
    """

    broker_type: BrokerType
    connection: StompConnectionSettings
    subscription: StompSubscriptionSettings
