"""
Type definitions related to django-stomp's configuration.

Headers must be typed dicts due to hyphened keys!
"""
from enum import Enum

from typing_extensions import TypedDict

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


class AcknowledgementType(Enum):
    """
    Ack types.
    """

    CLIENT: str = "client"
    CLIENT_INDIVIDUAL: str = "client-individual"
    AUTO: str = "auto"


class BrokerType(Enum):
    """
    Supported broker types
    """

    RABBITMQ: str = "rabbitmq"
    ACTIVEMQ: str = "activemq"
