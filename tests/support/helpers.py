import json
import re
import threading
from time import sleep
from typing import Dict
from uuid import uuid4

from django.core.serializers.json import DjangoJSONEncoder

from django_stomp.builder import build_listener
from django_stomp.builder import build_publisher
from django_stomp.helpers import clean_dict_with_falsy_or_strange_values
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import retry
from tests.support import rabbitmq
from tests.support.activemq.queue_details import current_queue_configuration
from tests.support.dtos import CurrentDestinationStatus


def get_destination_metrics_from_broker(destination_name: str) -> CurrentDestinationStatus:
    """
    Retrieves metrics from the broker management console regardless of the broker engine
    ActiveMQ or RabbitMQ.
    """
    try:
        destination_metrics = current_queue_configuration(destination_name)
    except Exception:
        destination_metrics = rabbitmq.current_queue_configuration(destination_name)  # type: ignore

    return destination_metrics


def publish_without_correlation_id_header(destination: str, body: Dict, attempt=1, persistent=True):
    """
    Publishes a message without correlation-id on the headers.
    """
    publisher = build_publisher()

    standard_header = {
        "tshoot-destination": destination,
        # RabbitMQ
        # These two parameters must be set on consumer side as well, otherwise you'll get precondition_failed
        "x-dead-letter-routing-key": create_dlq_destination_from_another_destination(destination),
        "x-dead-letter-exchange": "",
    }

    if persistent:
        standard_header.update({"persistent": "true"})

    send_params = {
        "destination": destination,
        "body": json.dumps(body, cls=DjangoJSONEncoder),
        "headers": standard_header,
        "content_type": "application/json;charset=utf-8",
        "transaction": getattr(publisher, "_tmp_transaction_id", None),
    }
    send_params = clean_dict_with_falsy_or_strange_values(send_params)

    def _internal_send_logic():
        publisher.start_if_not_open()
        publisher.connection.send(**send_params)

    retry(_internal_send_logic, attempt=attempt)


def publish_to_destination(
    destination: str, body: Dict, headers: Dict = None, persistent: bool = True, attempts: int = 1
) -> None:
    """
    Publishes a message to a destination.
    """
    with build_publisher(f"random-publisher-{uuid4()}").auto_open_close_connection() as publisher:
        publisher.send(body=body, queue=destination, headers=headers, persistent=persistent, attempt=attempts)


def get_latest_message_from_destination_using_test_listener(destination: str) -> Dict:
    """
    Gets the latest message using the test listener utility. It does not ack the message
    on the destination queue.

    [!]: It makes a test hang forever if a message never arrives at the destination.
    """
    evaluation_consumer = build_listener(destination, is_testing=True)
    test_listener = evaluation_consumer._test_listener
    evaluation_consumer.start(wait_forever=False)

    # may wait forever if the msg never arrives
    test_listener.wait_for_message()
    received_message = test_listener.get_latest_message()

    return received_message


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
