"""
Module with testing callbacks used for the tests.
"""
import logging
from math import ceil
import multiprocessing as mp
import os
import signal
import threading
from time import sleep
from typing import Callable

from django import db

from django_stomp.builder import build_publisher
from django_stomp.services.consumer import Payload
from tests.support.models import Simple

callback_move_and_ack_path = "tests.support.callbacks_for_tests.callback_move_and_ack"
callback_standard_path = "tests.support.callbacks_for_tests.callback_standard"
callback_with_exception_path = "tests.support.callbacks_for_tests.callback_with_exception"
callback_with_sleep_three_seconds_while_heartbeat_thread_is_alive_path = (
    "tests.support.callbacks_for_tests.callback_with_sleep_three_seconds_while_heartbeat_thread_is_alive"
)
callback_with_logging_path = "tests.support.callbacks_for_tests.callback_with_logging"
callback_with_sleep_three_seconds_path = "tests.support.callbacks_for_tests.callback_with_sleep_three_seconds"
callback_with_sleep_three_seconds_with_sigterm_path = (
    "tests.support.callbacks_for_tests.callback_with_sleep_three_seconds_with_sigterm"
)
callback_with_sleep_a_seconds_with_sigterm_path = (
    "tests.support.callbacks_for_tests.callback_with_sleep_a_seconds_with_sigterm"
)
callback_with_sleep_a_seconds_with_sigint_path = (
    "tests.support.callbacks_for_tests.callback_with_sleep_a_seconds_with_sigint"
)
callback_with_sleep_a_seconds_with_sigquit_path = (
    "tests.support.callbacks_for_tests.callback_with_sleep_a_seconds_with_sigquit"
)
callback_with_another_log_message_path = "tests.support.callbacks_for_tests.callback_with_another_log_message"
callback_with_nack_path = "tests.support.callbacks_for_tests.callback_with_nack"
callback_with_explicit_db_connection_path = "tests.support.callbacks_for_tests.callback_with_explicit_db_connection"


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


def callback_with_sleep_three_seconds_while_heartbeat_thread_is_alive(payload: Payload) -> None:
    logger = logging.getLogger(__name__)
    logger.info("I'll process the message: %s!", payload.body)

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


def _callback_with_sleep_n_seconds_with_signal(
    signal: signal.Signals, wait_time: float = 0.5, iterations: int = 5
) -> Callable:
    def _fn(payload: Payload) -> None:
        iteration = 1
        while True:
            if iteration == ceil(iterations / 2):
                p_kill = mp.Process(target=os.kill, args=(os.getpid(), signal.SIGTERM))
                p_kill.start()

            if iteration == iterations:
                break

            iteration += 1
            sleep(wait_time)

        payload.ack()
        logger = logging.getLogger(__name__)
        logger.info("%s sucessfully processed!", payload.body)

    return _fn


def callback_with_sleep_a_seconds_with_sigterm(payload: Payload) -> None:
    fn = _callback_with_sleep_n_seconds_with_signal(signal.SIGTERM, iterations=1)
    return fn(payload)


def callback_with_sleep_a_seconds_with_sigquit(payload: Payload) -> None:
    fn = _callback_with_sleep_n_seconds_with_signal(signal.SIGQUIT, iterations=1)
    return fn(payload)


def callback_with_sleep_a_seconds_with_sigint(payload: Payload) -> None:
    fn = _callback_with_sleep_n_seconds_with_signal(signal.SIGINT, iterations=1)
    return fn(payload)


def callback_with_sleep_three_seconds_with_sigterm(payload: Payload) -> None:
    fn = _callback_with_sleep_n_seconds_with_signal(signal.SIGTERM, 1)
    return fn(payload)


def callback_with_explicit_db_connection(payload: Payload):
    """
    This callback do a DB interaction and set a new attribute (`db`) in the thread that it's running
    so that any test can have a direct access to a `DatabaseWrapper`[1] and make assertions with it. This
    new attribute was needed due to the way Django works estabilishing a new DB connection for each
    thread [2].

    Note: The `db.connections` object is a handler (with a dict-like syntax), see [3] for more information
    on it!

    [1] https://github.com/django/django/blob/ca9872905559026af82000e46cde6f7dedc897b6/django/db/backends/base/base.py#L26
    [2] https://docs.djangoproject.com/en/3.2/ref/databases/#caveats
    [3] https://github.com/django/django/blob/ca9872905559026af82000e46cde6f7dedc897b6/django/db/utils.py#L134
    """
    Simple.objects.create()

    thread = threading.current_thread()
    setattr(thread, "db", db.connections["default"])

    payload.ack()
