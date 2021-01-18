"""
Base listener that satisfies stomp.py's listener event-driven contract to react upon events such as
on_message, on_error, on_disconnected (graceful reconnects), etc.
"""
import json
import logging
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Dict

from stomp.listener import TestListener

from django_stomp.services.subscribe.stomp11.context import ContextSubscriber11
from django_stomp.services.subscribe.stomp11.context import StompContext11

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Payload:
    ack: Callable
    nack: Callable
    headers: Dict
    body: Dict


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

    def on_error(self, headers: Dict, message_body: bytes) -> None:
        """
        Handles error frames received by the broker.
        """
        print(headers)
        print(message_body)

    def on_disconnected(self) -> None:
        """
        Gracefully handles disconnections to the broker.
        """
        logger.info("Listener has been disconnected from broker. Restaring...")
        self.subscribe(block_main_thread_period=1)  # 1s just to append listener again to conn


class TestListener11(TestListener, ContextSubscriber11):
    """
    Test listener for STOMP 1.1.
    """

    def __init__(self, stomp_context: StompContext11, receipt=None, print_to_log=None):
        TestListener.__init__(self, receipt, print_to_log)
        ContextSubscriber11.__init__(self, stomp_context)
