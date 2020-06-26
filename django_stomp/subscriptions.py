import logging
import uuid
from time import sleep
from typing import Any
from typing import Callable
from typing import Optional

from django_stomp.builder import build_listener
from django_stomp.exceptions import CorrelationIdNotProvidedException
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import get_listener_client_id
from django_stomp.helpers import get_subscription_destination
from django_stomp.helpers import is_destination_from_virtual_topic
from django_stomp.services.consumer import Listener
from django_stomp.services.consumer import Payload
from request_id_django_log import local_threading
from tenacity import retry
from tenacity.wait import wait_fixed

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


def subscribe_forever(listener: Listener, callback: Callable, wait_before_reconnect: float = 10) -> None:
    """
    Subscription for testing or forever.
    """
    while True:
        try:
            # callback subscription (execution on another thread)
            listener.start(callback, wait_forever=True)

        except BaseException as e:
            logger.exception(f"A exception of type {type(e)} was captured during listener logic")

        finally:
            logger.info(f"Trying to close listener...")

            if listener.is_open():
                listener.close()

            logger.info(f"Waiting {wait_before_reconnect} seconds before trying to connect again...")
            sleep(wait_before_reconnect)


@retry(stop=3, wait=wait_fixed(0.2))
def subscribe_for_testing(
    listener: Listener, callback: Callable, testing_disconnect: bool = False, wait_before_reconnect: float = 0.2,
) -> None:
    """
    Subscription for testing only. In case of exceptions, 3 retries are attempted.
    """
    listener.start(callback, wait_forever=False)  # callback subscription (execution on another thread)

    if testing_disconnect and listener.is_open():
        listener.close()


def start_subscription(
    listener: Listener,
    callback: Callable,
    is_testing: bool = False,
    testing_disconnect: bool = True,
    wait_before_reconnect: float = 10,
) -> None:
    """
    Subscribes the listener with its callback to a destination either for testing or forever.
    """
    if is_testing:
        subscribe_for_testing(listener, callback, testing_disconnect)

    else:
        subscribe_forever(listener, callback)  # must loop forever trying to reconnect
