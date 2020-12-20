"""
Base listener that satisfies stomp.py's listener event-driven contract to react upon events such as
on_message, on_error, on_disconnected (graceful reconnects), etc.
"""
import json
import logging
import time
from typing import Any
from typing import Callable
from typing import Dict

from stomp.connect import StompConnection11
from stomp.listener import TestListener
from stomp.utils import Frame

from django_stomp.services.consumer import Payload
from django_stomp.settings.types import StompConnectionSettings
from django_stomp.settings.types import StompSubscriptionSettings

logger = logging.getLogger(__name__)


class StompContext11:
    """
    Stomp's connection and subscription context based on STOMP 1.1 protocol.
    """

    stomp_connection_settings = StompConnectionSettings
    stomp_subscription_settings = StompSubscriptionSettings
    stomp_connection: StompConnection11

    def __init__(
        self,
        stomp_connection_settings: StompConnectionSettings,
        stomp_subscription_settings: StompSubscriptionSettings,
    ):
        self.stomp_connection_settings = stomp_connection_settings
        self.stomp_subscription_settings = stomp_subscription_settings
        self.stomp_connection = self._create_stomp_connection()

    def _create_stomp_connection(self) -> StompConnection11:
        """
        Creates the actual socket connection to the remote STOMP-compliant broker server.
        """
        conn = StompConnection11(
            self.stomp_connection_settings.hosts_and_ports,
            self.stomp_connection_settings.use_ssl,
            self.stomp_connection_settings.ssl_version,
            self.stomp_connection_settings.hosts_and_ports,
            self.stomp_connection_settings.vhost,
        )

        return conn


class ContextSubscriber11:
    """
    Adds subscription behavior to stomp listeners according to a stomp context (server settings, etc.) based on
    STOMP 1.1 protocol.
    """

    stomp_context: StompContext11

    def __init__(self, stomp_context: StompContext11) -> None:
        self.stomp_context = stomp_context

    def subscribe(self, block_main_thread: bool = True, block_main_thread_period: int = 0) -> None:
        """
        Uses the listener connection to connect and subscribe the listener with its event-driven methods
        to handle messages.
        """
        logger.info(
            f"Listener ID: {self.stomp_context.stomp_subscription_settings.listener_client_id} "
            f"Subscription ID: {self.stomp_context.stomp_subscription_settings.subscription_id}"
        )

        logger.info("Setting listener on the STOMP connection...")
        self.stomp_context.stomp_connection.set_listener(
            self.stomp_context.stomp_subscription_settings.listener_client_id, self
        )

        logger.info("Connecting and subscribing listener on separate receiver thread...")
        self.stomp_context.stomp_connection.connect(
            username=self.stomp_context.stomp_connection_settings.username,
            passcode=self.stomp_context.stomp_connection_settings.passcode,
            wait=self.stomp_context.stomp_connection_settings.wait,
            headers=self.stomp_context.stomp_connection_settings.headers,
        )

        self.stomp_context.stomp_connection.subscribe(
            destination=self.stomp_context.stomp_subscription_settings.destination,
            id=self.stomp_context.stomp_subscription_settings.subscription_id,
            ack=self.stomp_context.stomp_subscription_settings.ack_type.value,
            headers=self.stomp_context.stomp_connection_settings.headers,  # TODO: review this later
            **self.stomp_context.stomp_subscription_settings.headers,
        )

        while block_main_thread:

            # allows blocking for some period of time: can be useful for testing
            if block_main_thread_period > 0:
                time.sleep(block_main_thread_period)
                return

            time.sleep(1)


class StompListener11(ContextSubscriber11):
    """
    Event-driven listener that implements methods to react upon some events. Based
    on the STOMP 1.1 protocol and connection classes from stomp.py.
    """

    stomp_listener_callback: Any

    def __init__(self, stomp_listener_callback: Callable, stomp_context: StompContext11) -> None:
        ContextSubscriber11.__init__(self, stomp_context)
        self.stomp_listener_callback = stomp_listener_callback

    def on_message(self, headers: Dict, message_body: bytes) -> None:
        """
        The actual message handler of the listener. This should receive the users' callbacks.
        """

        def _ack_logic_closure():
            self.stomp_context.stomp_connection.ack(
                headers["message-id"], self.stomp_context.stomp_subscription_settings.subscription_id
            )

        def _nack_logic_closure():
            self.stomp_context.stomp_connection.nack(
                headers["message-id"], self.stomp_context.stomp_subscription_settings.subscription_id, requeue=False,
            )

        # payload is a helper class which is used by the callback
        payload = Payload(_ack_logic_closure, _nack_logic_closure, headers, json.loads(message_body))
        self.stomp_listener_callback(payload)  # TODO: workpool for heartbeat

    def on_error(self, frame: Frame) -> None:
        """
        Handles error frames received by the broker.
        """
        pass

    def on_disconnected(self) -> None:
        """
        Gracefully handles disconnections to the broker.
        """
        logger.info("Listener has been disconnected from broker. Restaring...")
        self.subscribe(block_main_thread=False)


class TestListener11(TestListener, ContextSubscriber11):
    """
    Test listener for STOMP 1.1.
    """

    def __init__(self, stomp_context: StompContext11, receipt=None, print_to_log=None):
        TestListener.__init__(self, receipt, print_to_log)
        ContextSubscriber11.__init__(self, stomp_context)
