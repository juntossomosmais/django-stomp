"""
Base listener that satisfies stomp.py's listener event-driven contract to react upon events such as
on_message, on_error, on_disconnected (graceful reconnects), etc.
"""
import json
import logging
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

from stomp.connect import StompConnection11
from stomp.utils import Frame
from typing_extensions import TypedDict

from django_stomp.helpers import display_heartbeat_warning_if_necessary
from django_stomp.services.consumer import Payload
from django_stomp.services.settings_scanner import DjangoStompSettings

logger = logging.getLogger(__name__)


class BaseStompListener:
    """
    Event-driven listener that implements methods to react upon some events.
    """

    def __init__(self, stomp_connection: Any) -> None:
        """
        Saves initial state for the listener.
        """
        pass

    def start(self) -> None:
        """
        Uses the listener connection to connect and subscribe the listener with its event-driven methods
        to handle messages.
        """
        pass

    def on_message(self, headers: Dict, message_body: bytes) -> None:
        """
        The actual message handler of the listener. This should receive the users' callbacks.
        """
        pass

    def on_error(self, frame: Frame) -> None:
        """
        Handles error frames received by the broker.
        """
        pass

    def on_disconnected(self) -> None:
        """
        Gracefully handles disconnections to the broker.
        """
        pass


# ---- StompSubscriptionDetailsRabbitMQ ---- #

StompSubscriptionDetailsActiveMQ = TypedDict("StompSubscriptionDetailsActiveMQ", {"ack": str, "destination": str})
StompSubscriptionDetailsRabbitMQ = TypedDict(
    "StompSubscriptionDetailsRabbitMQ",
    {"ack": str, "destination": str, "x-queue-name": str, "auto-delete": bool, "durable": bool},
)

# ---- StompConnectFrameSettings ---- # headers also sued by subscription
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

StompConnectFrameSettings = TypedDict(
    "StompConnectFrameSettings",
    {
        "username": str,
        "passcode": str,
        "wait": bool,
        "headers": Union[ConnectionHeadersRabbitMQ, ConnectionHeadersActiveMQ],
    },
)

# ---- StompConnectionSettings ---- #
StompConnectionSettings = TypedDict(
    "StompConnectionSettings",
    {
        "hosts_and_ports": List[Tuple[str, int]],
        "use_ssl": bool,
        "ssl_version": int,
        "heartbeats": Tuple[int, int],
        "vhost": str,
    },
)

# conn.start() -> actual socket connection -> StompSocketConnectionSettings
# conn.connect() -> sends CONNECT frame to the broker -> StompConnectFrameSettings


class ListenerRabbitMQ(BaseStompListener):
    """
    Event-driven listener that implements methods to react upon some events.
    """

    stomp_subscription_details: StompSubscriptionDetailsRabbitMQ
    stomp_connection_settings: StompConnectionSettings
    stomp_connect_frame_settings: StompConnectFrameSettings
    stomp_connection: StompConnection11
    stomp_listener_id: str
    stomp_subscription_id: str
    stomp_listener_callback: Any

    def __init__(
        self,
        stomp_listener_callback: Callable,
        stomp_connection_settings: StompConnectionSettings,
        stomp_connect_frame_settings: StompConnectFrameSettings,
        stomp_subscription_details: StompSubscriptionDetailsRabbitMQ,
        stomp_listener_id: str,
        stomp_subscription_id: str,
    ) -> None:
        self.stomp_connection_settings = stomp_connection_settings
        self.stomp_connect_frame_settings = stomp_connect_frame_settings
        self.stomp_connection = self._create_stomp_connection(stomp_connection_settings)
        self.stomp_subscription_details = stomp_subscription_details
        self.stomp_listener_id = stomp_listener_id
        self.stomp_subscription_id = stomp_subscription_id
        self.stomp_listener_callback = stomp_listener_callback

    def _create_stomp_connection(self, stomp_connection_settings: StompConnectionSettings) -> StompConnection11:
        """
        Creates the actual socket connection to the remote STOMP-compliant server.
        """
        return StompConnection11(
            stomp_connection_settings["hosts_and_ports"],
            use_ssl=stomp_connection_settings["use_ssl"],
            ssl_version=stomp_connection_settings["ssl_version"],
            heartbeats=stomp_connection_settings["heartbeats"],
            vhost=stomp_connection_settings["vhost"],
        )

    def _process_message_with_callback(self, callback: Callable, headers: Dict, message_body: bytes):
        """
        Creates a helper Payload class with the headers and message body and sends it to be processed by
        the callback supplied by the users.
        """
        # closures used for the Payload class to allow easy of use inside the callback functions
        def _ack_logic_closure(self):
            self.stomp_connection.ack(headers["message-id"], self.stomp_subscription_id)

        def _nack_logic_closure(self):
            self.stomp_connection.nack(headers["message-id"], self.stomp_subscription_id, requeue=False)

        # payload is a helper class which is used by the callback
        payload = Payload(_ack_logic_closure, _nack_logic_closure, headers, json.loads(message_body))

        self.stomp_listener_callback(payload)  # TODO: workpool for heartbeat

    def start(self) -> None:
        """
        Uses the listener connection to connect and subscribe the listener with its event-driven methods
        to handle messages.
        """
        logger.info(f"Listener ID: {self.stomp_listener_id}\nSubscription ID: {self.stomp_subscription_id}")
        logger.info("Connecting and subscribing...")

        self.stomp_connection.set_listener(self.stomp_listener_id, self)  # sets this class itself as a listener
        self.stomp_connection.connect(self.stomp_connection_settings)  # sends CONNECT frame
        self.stomp_connection.subscribe(
            id=self.stomp_listener_id,
            headers=self.stomp_connect_frame_settings["headers"],
            **self.stomp_subscription_details,
        )

    def on_message(self, headers: Dict, message_body: bytes) -> None:
        """
        The actual message handler of the listener. This should receive the users' callbacks.
        """
        self._process_message_with_callback(self.stomp_listener_callback, headers, message_body)

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
        self.start()


def build_stomp_connection_settings(settings: DjangoStompSettings) -> StompConnectionSettings:
    hosts_and_ports = [(settings.stomp_server_host, settings.stomp_server_port)]

    if settings.stomp_server_standby_host and settings.stomp_server_standby_port:
        hosts_and_ports.append((settings.stomp_server_standby_host, settings.stomp_server_standby_port))

    logger.info(
        f"Use SSL? {settings.use_ssl}. Version: {settings.ssl_version}. Outgoing/Ingoing heartbeat: "
        f"{settings.outgoing_heartbeat}/{settings.incoming_heartbeat}. "
        f"Background? {settings.should_process_msg_on_background}"
    )

    display_heartbeat_warning_if_necessary(settings)

    return {
        "hosts_and_ports": hosts_and_ports,
        "use_ssl": settings.use_ssl,
        "ssl_version": settings.ssl_version,
        "heartbeats": (settings.outgoing_heartbeat, settings.incoming_heartbeat),
        "vhost": settings.vhost,
    }


def build_stomp_connect_frame_settings(
    connection_headers: Union[ConnectionHeadersRabbitMQ, ConnectionHeadersActiveMQ], settings: DjangoStompSettings,
) -> StompConnectFrameSettings:
    return {
        "username": settings.stomp_server_user,
        "passcode": settings.stomp_server_password,
        "wait": True,
        "headers": connection_headers,
    }


def build_connection_headers_rabbitmq(
    x_dead_letter_routing_key: str, x_dead_letter_exchange: str, prefetch_count: int = 1
) -> ConnectionHeadersRabbitMQ:
    return {
        "prefetch-count": str(prefetch_count),
        "x-dead-letter-routing-key": x_dead_letter_routing_key,
        "x-dead-letter-exchange": x_dead_letter_exchange,
    }


def build_subscription_details_rabbitmq(
    ack: str, destination: str, x_queue_name: str, auto_delete: bool, durable: bool
) -> StompSubscriptionDetailsRabbitMQ:
    return {
        "ack": ack,
        "destination": destination,
        "x-queue-name": x_queue_name,
        "auto-delete": auto_delete,
        "durable": durable,
    }
