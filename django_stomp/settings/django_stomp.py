"""
Modules with DTOs and other data structures used to contain settings data.
"""

import logging
from dataclasses import dataclass
from typing import List
from typing import Tuple
from typing import Union

from django_stomp.settings.types import AcknowledgementType
from django_stomp.settings.types import BrokerType
from django_stomp.settings.types import ConnectionHeadersActiveMQ
from django_stomp.settings.types import ConnectionHeadersRabbitMQ
from django_stomp.settings.types import StompSubscriptionHeadersActiveMQ
from django_stomp.settings.types import StompSubscriptionHeadersRabbitMQ

logger = logging.getLogger(__name__)


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
