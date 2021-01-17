"""
Module with adapters required to deal with broker-specific headers.
"""
from typing import Dict

from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import only_destination_name
from django_stomp.settings.types import StompSettings


class BrokerAdapter:
    """
    Generic broker adapter to CONNECT and SUBSCRIBE Stomp frames.
    """

    def __init__(self, settings: StompSettings):
        self.settings = settings

    def build_connection_headers(self) -> Dict:
        raise NotImplementedError

    def build_subscription_headers(self) -> Dict:
        raise NotImplementedError


class BrokerAdapterRabbitMQ(BrokerAdapter):
    """
    Adapter used to build appropriate headers for CONNECT and SUBSCRIBE Stomp frames when using
    a RabbitMQ broker.
    """

    def build_connection_headers(self):
        default_headers = {}

        # user extra headers take preference to override everything
        return {**default_headers, **self.settings.connection.extra_headers}

    def build_subscription_headers(self) -> Dict:
        destination = self.settings.subscription.destination

        default_headers = {
            "prefetch-count": 1,
            "x-queue-name": only_destination_name(destination),
            "auto-delete": False,
            "durable": True,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": create_dlq_destination_from_another_destination(destination),
        }

        # user extra headers take preference to override everything
        return {**default_headers, **self.settings.subscription.extra_headers}


class BrokerAdapterActiveMQ(BrokerAdapter):
    """
    Adapter used to build appropriate headers for CONNECT and SUBSCRIBE Stomp frames when using
    an ActiveMQ broker.
    """

    def build_connection_headers(self):
        default_headers = {
            "client-id": self.settings.connection.listener_client_id,
        }

        # user extra headers take preference to override everything
        return {**default_headers, **self.settings.connection.extra_headers}

    def build_subscription_headers(self) -> Dict:
        listener_client_id = (self.settings.connection.listener_client_id,)

        default_headers = {
            "activemq.prefetchSize": 1,
            "activemq.subscriptionName": f"{listener_client_id}-listener",  # ActiveMQ 5.x
            "activemq.subcriptionName": f"{listener_client_id}-listener",  # ActiveMQ 4.x (misspelled)
        }

        # user extra headers take preference to override everything
        return {**default_headers, **self.settings.subscription.extra_headers}
