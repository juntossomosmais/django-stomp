"""
Base listener that satisfies stomp.py's listener event-driven contract to react upon events such as
on_message, on_error, on_disconnected (graceful reconnects), etc.
"""
from typing import Any
from stomp.utils import Frame


class BaseStompListener:
    """
    Event-driven listener that implements methods to react upon some events.
    """

    def __init__(self, stomp_connection: Any) -> None:
        """
        Saves initial state for the listener.
        """
        pass

    def connect_and_subscribe(self) -> None:
        """
        Uses the listener connection to connect and subscribe the listener with its event-driven methods
        to handle messages.
        """
        pass

    def on_message(self, frame: Frame) -> None:
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
