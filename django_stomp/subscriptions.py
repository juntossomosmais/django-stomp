import logging
import uuid
from typing import Any
from typing import Callable
from typing import Optional

from django.utils.module_loading import import_string
from request_id_django_log import local_threading

from django_stomp.builder import build_listener
from django_stomp.exceptions import CorrelationIdNotProvidedException
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import get_listener_client_id
from django_stomp.helpers import get_subscription_destination
from django_stomp.helpers import is_destination_from_virtual_topic
from django_stomp.services.consumer import Payload
from django_stomp.services.listener import StompContext11
from django_stomp.services.listener import StompListener11
from django_stomp.settings.django_stomp import compile_django_stomp_settings
from django_stomp.settings.types import BrokerType

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


def listener_callback_factory(
    stomp_context: StompContext11,
    execution_callback: Callable,
    param_to_callback: Any,
    is_correlation_id_required: bool,
) -> Callable[[Payload], None]:
    """
    Factory used to wrap user callbacks with some extra logic.
    """
    # closure: defined in a lexical scope where listener and other vars are defined
    def _callback_closure(payload: Payload) -> None:
        try:

            local_threading.request_id = get_or_create_correlation_id(payload.headers, is_correlation_id_required)

            if param_to_callback:
                execution_callback(payload, param_to_callback)
            else:
                execution_callback(payload)

        except Exception as e:

            logger.exception(f"A exception of type {type(e)} was captured during callback logic")
            logger.warning("Trying to do NACK explicitly sending the message to DLQ...")

            if stomp_context.stomp_connection.is_connected():
                payload.nack()
                logger.warning("Done!")
            raise e

        finally:
            local_threading.request_id = None

    return _callback_closure


def subscribe_listener(
    destination_name: str, callback_import_path: str, param_to_callback: Any, subscription_period: Optional[int]
) -> None:
    """
    Subscribes listener forever to its destination by blocking the main thread.
    """

    settings = compile_django_stomp_settings(destination_name)
    callback_function = import_string(callback_import_path)

    if settings.broker_type == BrokerType.RABBITMQ:
        create_dlq_queue(destination_name, settings.subscription_settings.listener_client_id)
        create_routing_key_bindings(destination_name, settings.subscription_settings.listener_client_id)

    stomp_context = StompContext11(settings.connection_settings, settings.subscription_settings)
    wrapped_callback = listener_callback_factory(
        stomp_context, callback_function, param_to_callback, settings.subscription_settings.is_correlation_id_required,
    )
    listener = StompListener11(wrapped_callback, stomp_context)

    if subscription_period is not None:
        listener.subscribe(block_main_thread=True, block_main_thread_period=subscription_period)
    else:
        listener.subscribe(block_main_thread=True)
