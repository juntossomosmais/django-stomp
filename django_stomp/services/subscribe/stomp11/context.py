"""
Stomp context required to create STOMP subscription.
"""
import logging
import time

from stomp.connect import StompConnection11

from django_stomp.services.subscribe.stomp11.adapter import BrokerAdapter
from django_stomp.settings.types import StompSettings

logger = logging.getLogger(__name__)


class StompContext11:
    """
    Stomp's connection and subscription context based on STOMP 1.1 protocol.
    """

    settings = StompSettings
    connection: StompConnection11
    broker_adapter: BrokerAdapter

    def __init__(self, stomp_settings: StompSettings, broker_adapter: BrokerAdapter):
        self.stomp_settings = stomp_settings
        self.broker_adapter = broker_adapter
        self.stomp_connection = self._create_stomp_connection()

    def _create_stomp_connection(self) -> StompConnection11:
        """
        Creates the actual socket connection to the remote STOMP-compliant broker server but does not
        send CONNECT or SUBSCRIBE Stomp frames.
        """
        conn = StompConnection11(
            self.stomp_settings.connection.hosts_and_ports,
            self.stomp_settings.connection.use_ssl,
            self.stomp_settings.connection.ssl_version,
            self.stomp_settings.connection.hosts_and_ports,
            self.stomp_settings.connection.vhost,
        )

        return conn


class ContextSubscriber11:
    """
    Adds subscription behavior to stomp listeners according to a stomp context (server settings, etc.) based on
    STOMP 1.1 protocol.
    """

    stomp_context: StompContext11  # fetches connection and destination name from the context

    def __init__(self, stomp_context: StompContext11) -> None:
        self.stomp_context = stomp_context

    def subscribe(self, block_main_thread_period: float = 0) -> None:
        """
        Uses the listener connection to connect and subscribe the listener with its event-driven methods
        to handle messages.
        """
        logger.info(
            f"Listener ID: {self.stomp_context.settings.connection.listener_client_id} "
            f"Subscription ID: {self.stomp_context.settings.subscription.subscription_id}"
        )

        logger.info("Setting listener on the STOMP connection...")
        self.stomp_context.stomp_connection.set_listener(
            self.stomp_context.settings.connection.listener_client_id, self
        )

        connection_headers = self.stomp_context.broker_adapter.build_connection_headers()
        logger.info("Created Stomp CONNECT headers: %s", connection_headers)

        subscription_headers = self.stomp_context.broker_adapter.build_subscription_headers()
        logger.info("Created Stomp SUBSXRIBE headers: %s", subscription_headers)

        logger.info("Connecting and subscribing listener on separate receiver thread...")
        self.stomp_context.stomp_connection.connect(
            username=self.stomp_context.settings.connection.username,
            passcode=self.stomp_context.settings.connection.passcode,
            wait=self.stomp_context.settings.connection.wait,
            headers=connection_headers,
        )

        self.stomp_context.stomp_connection.subscribe(
            destination=self.stomp_context.settings.subscription.destination,
            id=self.stomp_context.settings.subscription.subscription_id,
            ack=self.stomp_context.settings.subscription.ack_type.value,
            headers=subscription_headers,
        )

        if block_main_thread_period > 0:
            time.sleep(block_main_thread_period)
            return

        # sustains main thread forever with the listener connected on a background thread
        while True:
            time.sleep(1)
