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

from stomp import ConnectionListener
from stomp.connect import StompConnection11
from stomp.utils import Frame

from django_stomp.services.consumer import Payload
from django_stomp.settings import StompConnectionSettings
from django_stomp.settings import StompConnectionSettingsDetails
from django_stomp.settings import StompSubscriptionSettings

logger = logging.getLogger(__name__)


class StompContext:
    """
    Examples:

    >>> subscription_manager = StompContext()
    >>> listener = StompListener11()
    >>> testing_listener = TestingListener()

    >>> # testing without blocking
    >>> subscription_manager.subscribe(testing_listener, block_main_thread=False)
    >>> subscription_manager.stomp_listener.wait_for_message()


    >>> blocking main thread
    >>> subscription_manager.subscribe(listener, block_main_thread=True)


    >>> # blocks for 2 seconds only can be useful for testing some listeners
    >>> subscription_manager.subscribe(listener, block_main_thread_period=2)
    """

    MAIN_THREAD_SLEEP_TIME = 1

    stomp_connection_settings: StompConnectionSettings
    stomp_connection_settings_details: StompConnectionSettingsDetails
    stomp_connection: StompConnection11

    def __init__(
        self,
        stomp_connection_settings: StompConnectionSettings,
        stomp_connection_settings_details: StompConnectionSettingsDetails,
        stomp_subscription_settings: StompSubscriptionSettings,
    ):
        self.stomp_connection_settings = stomp_connection_settings
        self.stomp_connection_settings_details = stomp_connection_settings_details
        self.stomp_subscription_settings = stomp_subscription_settings
        self.stomp_connection = self._create_stomp_connection()

    def _create_stomp_connection(self) -> StompConnection11:
        """
        Creates the actual socket connection to the remote STOMP-compliant server.
        """
        conn = StompConnection11(
            self.stomp_connection_settings.hosts_and_ports,
            self.stomp_connection_settings.use_ssl,
            self.stomp_connection_settings.ssl_version,
            self.stomp_connection_settings.hosts_and_ports,
            self.stomp_connection_settings.vhost,
        )

        return conn

    def subscribe(
        self, stomp_listener: ConnectionListener, block_main_thread: bool = True, block_main_thread_period: int = 0
    ) -> None:
        """
        Uses the listener connection to connect and subscribe the listener with its event-driven methods
        to handle messages.
        """
        logger.info(
            f"Listener ID: {self.stomp_subscription_settings.listener_client_id} "
            f"Subscription ID: {self.stomp_subscription_settings.subscription_id}"
        )

        logger.info("Setting listener on the STOMP connection...")
        self.stomp_connection.set_listener(self.stomp_subscription_settings.listener_client_id, stomp_listener)

        logger.info("Connecting and subscribing listener on separate receiver thread...")
        self.stomp_connection.connect(
            username=self.stomp_connection_settings_details.username,
            passcode=self.stomp_connection_settings_details.passcode,
            wait=self.stomp_connection_settings_details.wait,
            headers=self.stomp_connection_settings_details.headers,
        )

        self.stomp_connection.subscribe(
            destination=self.stomp_subscription_settings.destination,
            id=self.stomp_subscription_settings.subscription_id,
            ack=self.stomp_subscription_settings.ack_type.value,
            headers=self.stomp_connection_settings_details.headers,  # TODO: review this later
            **self.stomp_subscription_settings.headers,
        )

        while block_main_thread:

            # allows blocking for some period of time: can be useful for testing
            if block_main_thread_period > 0:
                time.sleep(block_main_thread_period)
                return

            time.sleep(self.MAIN_THREAD_SLEEP_TIME)


class StompListener11:
    """
    Event-driven listener that implements methods to react upon some events. Based
    on the STOMP 1.1 protocol and connection classes from stomp.py.
    """

    stomp_context: StompContext
    stomp_listener_callback: Any

    def __init__(self, stomp_listener_callback: Callable, stomp_context: StompContext):
        self.stomp_listener_callback = stomp_listener_callback
        self.stomp_context = stomp_context

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
        self.stomp_context.subscribe(self, block_main_thread=False)


# class StompListener11:
#     """
#     Event-driven listener that implements methods to react upon some events. Based
#     on the STOMP 1.1 protocol and connection classes from stomp.py.
#     """

#     stomp_connection_settings: StompConnectionSettings
#     stomp_connection_settings_details: StompConnectionSettingsDetails
#     stomp_connection: StompConnection11

#     stomp_subscription_details: StompSubscriptionSettings
#     stomp_listener_callback: Any

#     def __init__(
#         self,
#         stomp_listener_callback: Callable,
#         stomp_connection_settings: StompConnectionSettings,
#         stomp_connection_settings_details: StompConnectionSettingsDetails,
#         stomp_subscription_settings: StompSubscriptionSettings,
#     ):
#         self.stomp_connection_settings = stomp_connection_settings
#         self.stomp_connection_settings_details = stomp_connection_settings_details
#         self.stomp_connection = self._create_stomp_connection()

#         self.stomp_subscription_settings = stomp_subscription_settings
#         self.stomp_listener_callback = stomp_listener_callback

#     def _create_stomp_connection(self) -> StompConnection11:
#         """
#         Creates the actual socket connection to the remote STOMP-compliant server.
#         """
#         conn = StompConnection11(
#             self.stomp_connection_settings.hosts_and_ports,
#             self.stomp_connection_settings.use_ssl,
#             self.stomp_connection_settings.ssl_version,
#             self.stomp_connection_settings.hosts_and_ports,
#             self.stomp_connection_settings.vhost,
#         )

#         return conn

#     def _process_message_with_callback(self, headers: Dict, message_body: bytes) -> None:
#         """
#         Creates a helper Payload class with the headers and message body and sends it to be processed by
#         the callback supplied by the users.
#         """
#         # closures used for the Payload class to allow easy of use inside the callback functions
#         def _ack_logic_closure(self):
#             self.stomp_connection.ack(headers["message-id"], self.stomp_subscription_settings.subscription_id)

#         def _nack_logic_closure(self):
#             self.stomp_connection.nack(
#                 headers["message-id"], self.stomp_subscription_settings.subscription_id, requeue=False
#             )

#         # payload is a helper class which is used by the callback
#         payload = Payload(_ack_logic_closure, _nack_logic_closure, headers, json.loads(message_body))
#         self.stomp_listener_callback(payload)  # TODO: workpool for heartbeat

#     def _connect_and_subscribe(self) -> None:
#         """
#         Creates the socket connection using the STOMP protocol and sends a SUBSCRIBE frame in order
#         to start receiving messages from a destination such as queue, topic, etc.
#         """
#         self.stomp_connection.connect(
#             username=self.stomp_connection_settings_details.username,
#             passcode=self.stomp_connection_settings_details.passcode,
#             wait=self.stomp_connection_settings_details.wait,
#             headers=self.stomp_connection_settings_details.headers,
#         )

#         self.stomp_connection.subscribe(
#             destination=self.stomp_subscription_settings.destination,
#             id=self.stomp_subscription_settings.subscription_id,
#             ack=self.stomp_subscription_settings.ack_type.value,
#             headers=self.stomp_connection_settings_details.headers,  # TODO: review this later
#             **self.stomp_subscription_settings.headers,
#         )

#     def start(self) -> None:
#         """
#         Uses the listener connection to connect and subscribe the listener with its event-driven methods
#         to handle messages.
#         """
#         logger.info(
#             f"Listener ID: {self.stomp_subscription_settings.listener_client_id} "
#             f"Subscription ID: {self.stomp_subscription_settings.subscription_id}"
#         )

#         logger.info("Setting listener on the STOMP connection...")
#         self.stomp_connection.set_listener(self.stomp_subscription_settings.listener_client_id, self)

#         logger.info("Connecting and subscribing listener on separate receiver thread...")
#         self._connect_and_subscribe()

#     def on_message(self, headers: Dict, message_body: bytes) -> None:
#         """
#         The actual message handler of the listener. This should receive the users' callbacks.
#         """
#         self._process_message_with_callback(headers, message_body)

#     def on_error(self, frame: Frame) -> None:
#         """
#         Handles error frames received by the broker.
#         """
#         pass

#     def on_disconnected(self) -> None:
#         """
#         Gracefully handles disconnections to the broker.
#         """
#         logger.info("Listener has been disconnected from broker. Restaring...")
#         self.start()
