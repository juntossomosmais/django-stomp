import logging
import uuid
from typing import Optional

from django_stomp.exceptions import CorrelationIdNotProvidedException
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import get_listener_client_id
from django_stomp.helpers import get_subscription_destination
from django_stomp.helpers import is_destination_from_virtual_topic

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
