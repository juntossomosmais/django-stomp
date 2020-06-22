"""
Module with testing callbacks used for the tests.
"""
import logging
import threading
from time import sleep
from typing import Callable
from uuid import uuid4

from django_stomp.builder import build_publisher
from django_stomp.services.consumer import Payload

callback_move_and_ack_path = "tests.support.callbacks_for_tests.callback_move_and_ack"
callback_standard_path = "tests.support.callbacks_for_tests.callback_standard"
callback_with_exception_path = "tests.support.callbacks_for_tests.callback_with_exception"
callback_with_sleep_three_seconds_while_heartbeat_thread_is_alive_path = (
    "tests.support.callbacks_for_tests.callback_with_sleep_three_seconds_while_heartbeat_thread_is_alive"
)
callback_with_logging_path = "tests.support.callbacks_for_tests.callback_with_logging"
callback_with_sleep_three_seconds_path = "tests.support.callbacks_for_tests.callback_with_sleep_three_seconds"
callback_with_another_log_message_path = "tests.support.callbacks_for_tests.callback_with_another_log_message"
callback_with_nack_path = "tests.support.callbacks_for_tests.callback_with_nack"


def callback_move_and_ack(payload: Payload, destination: str):
    """
    Callback for moving to another destination. Requires start_processing() to be called
    with param_to_callback.
    """
    publisher = build_publisher()
    publisher.send(payload.body, destination, attempt=1)
    payload.ack()


def callback_standard(payload: Payload):
    """
    Standard callback with simple ack.
    """
    # Should dequeue the message
    payload.ack()


def callback_with_nack(payload: Payload):
    payload.nack()


def callback_with_exception(payload: Payload):
    raise Exception("Lambe Sal")


def callback_with_sleep_three_seconds_while_heartbeat_thread_is_alive(payload: Payload):
    heartbeat_threads = [thread for thread in threading.enumerate() if "StompHeartbeatThread" in thread.name]
    while True:
        sleep(3)
        heartbeat_threads = filter(lambda thread: "StompHeartbeatThread" in thread.name, threading.enumerate())
        if all(not thread.is_alive() for thread in heartbeat_threads):
            break


def callback_with_logging(payload: Payload):
    logger = logging.getLogger(__name__)
    logger.info("I'll process the message: %s!", payload.body)
    payload.ack()


def callback_with_another_log_message(payload: Payload):
    logger = logging.getLogger(__name__)
    logger.info("%s is the message that I'll process!", payload.body)
    payload.ack()


def callback_with_sleep_three_seconds(payload: Payload):
    sleep(3)
    payload.ack()
    logger = logging.getLogger(__name__)
    logger.info("%s sucessfully processed!", payload.body)
