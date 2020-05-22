import re
import threading
from time import sleep

from tests.support import rabbitmq


def iterable_len(iterable):
    """
    Calculates the length of any iterable (iterators included!)
    """
    return sum(1 for _ in iterable)


def wait_for_message_in_log(caplog, message_to_wait, message_count_to_wait=None, max_seconds_to_wait=None):
    """
    Awaits for a message that must appears for a given number of times.

    Args:
        caplog: An instance of LogCaptureFixture from pytest that is used to retrieve a list of
            format-interpolated log messages.
            Refer to: https://docs.pytest.org/en/latest/reference.html#_pytest.logging.LogCaptureFixture
        message_to_wait: A string message that'll be searched in the logs.
        message_count_to_wait: Optionally integer parameter that indicates how many `message_to_wait` we
            need to find in the logs. Defaults to 1.
        max_seconds_to_wait: Optionally integer parameter that indicates how many seconds the search will
            awaits for the messages appears in the logs. Defaults to 5 seconds
    """
    max_seconds_to_wait = max_seconds_to_wait or 5
    message_count_to_wait = message_count_to_wait or 1

    while max_seconds_to_wait:
        message_in_logs_count = iterable_len(
            filter(lambda message: re.compile(message_to_wait).match(message), caplog.messages)
        )
        if message_in_logs_count == message_count_to_wait:
            break
        max_seconds_to_wait -= 1
        sleep(1)


def get_active_threads_name_with_prefix(prefix: str):
    """
    Retrieves the threads name that starts with `prefix` and are active.
    """
    prefix_regex = re.compile(f"^{prefix}")
    return [thread.name for thread in threading.enumerate() if prefix_regex.match(thread.name)]


def is_testing_against_rabbitmq() -> bool:
    """
    Verify if the test suite is running against RabbitMQ.
    """
    try:
        rabbitmq.get_broker_version()
        return True
    except Exception:
        return False
