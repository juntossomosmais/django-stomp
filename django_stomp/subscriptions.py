import logging
import uuid
from typing import Callable
from typing import Optional

from django_stomp.builder import build_listener
from django_stomp.exceptions import CorrelationIdNotProvidedException
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import get_listener_client_id
from django_stomp.helpers import get_subscription_destination
from django_stomp.helpers import is_destination_from_virtual_topic
from django_stomp.services.consumer import Listener

logger = logging.getLogger(__name__)


def get_or_create_correlation_id(headers: dict, is_correlation_id_required: bool) -> str:
    """
    Attempts to extract correlation_id from headers. If is_correlation_id_required = True, then
    it raises an exception if this header is not found.
    """
    if "correlation-id" in headers:
        return headers["correlation-id"]

    if not is_correlation_id_required:
        correlation_id = uuid.uuid4()
        logger.info(f"New correlation-id was generated {correlation_id}")
        return str(correlation_id)

    raise CorrelationIdNotProvidedException(headers)


def create_queue(
    queue_name: str,
    listener_client_id: str,
    durable_topic_subscription: bool = False,
    routing_key: Optional[str] = None,
):
    """
    Queue creation based on creating a listener connection to the destination and closing it right after.
    """
    client_id = get_listener_client_id(durable_topic_subscription, listener_client_id)
    listener = build_listener(queue_name, durable_topic_subscription, client_id=client_id, routing_key=routing_key)

    listener.start(lambda payload: None, wait_forever=False)
    listener.close()


def create_dlq_queue(destination_name: str, listener_client_id: str):
    """
    Creates DLQ queues by adding a prefix to the destination name.
    """
    dlq_destination_name = create_dlq_destination_from_another_destination(destination_name)

    create_queue(dlq_destination_name, listener_client_id)
    logger.info("Created/Refreshed DLQ in case of RabbitMQ...")


def create_routing_key_bindings(destination_name: str, listener_client_id: str) -> None:
    """
    Due to STOMP and its RabbitMQ plugin, messages to queues are always sent to the default exchange
    which all queues are bound to via a routing key that is the queue name. So, for queues, the binding
    is automatically done by RabbitMQ without any effort of this lib.

    However, for topics messages are sent to the amq.topic topic exchange which requires routing key bindings.
    In this method, the topic name is used as the routing key to create bindings for each queue that receives
    messages from the topic.
    """
    if is_destination_from_virtual_topic(destination_name):
        routing_key = get_subscription_destination(destination_name)

        create_queue(destination_name, listener_client_id, routing_key=routing_key)
        logger.info("Created/Refreshed queue to consume from topic in case of RabbitMQ...")


def subscribe_forever(listener: Listener, callback: Callable) -> None:
    """
    Subscribes forever. Uses stomp.py to append the listener argument to STOMP connection which is run, forever,
    on a secondary thread. This main thread is locked forever with a forever true loop that attempts to reconnect
    if the listener becomes offline for some reason.
    """
    listener.start(callback, wait_forever=True)


def subscribe_for_testing(
    listener: Listener, callback: Callable, subscription_duration: float = 0.4, disconnect_after_tests: bool = True
) -> None:
    """
    Subscribes to a destination for a fixed period of time. Used by test cases where subscription should last for
    some time and then finish. The subscription, as usual, occurs on another thread, but is sustained by the main
    main thread for 'subscription_duration' seconds.
    """
    listener.start(callback, wait_forever=False, subscription_duration=subscription_duration)

    if listener.is_open() and disconnect_after_tests:  # TODO: check this later
        listener.close()
