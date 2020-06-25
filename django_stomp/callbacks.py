"""
Module with callback-related definitions used on SUBSCRIPTIONS.
"""
import logging
import uuid
from time import sleep
from typing import Any
from typing import Callable
from typing import Optional

from django_stomp.builder import build_listener
from django_stomp.builder import build_publisher
from django_stomp.exceptions import CorrelationIdNotProvidedException
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import get_listener_client_id
from django_stomp.helpers import get_subscription_destination
from django_stomp.helpers import is_destination_from_virtual_topic
from django_stomp.helpers import remove_key_from_dict
from django_stomp.services.consumer import Listener
from django_stomp.services.consumer import Payload
from django_stomp.subscriptions import get_or_create_correlation_id
from request_id_django_log import local_threading

logger = logging.getLogger(__name__)


def callback_factory(
    listener, execution_callback: Callable, param_to_callback: Any, is_correlation_id_required: bool
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

        except BaseException as e:

            logger.exception(f"A exception of type {type(e)} was captured during callback logic")
            logger.warning("Trying to do NACK explicitly sending the message to DLQ...")

            if listener.is_open():
                payload.nack()
                logger.warning("Done!")
            raise e

        finally:
            local_threading.request_id = None

    return _callback_closure


def callback_for_cleaning_queues(payload: Payload):
    """
    Callback that just acks all messages on a queue for cleaning it.
    """
    headers = payload.headers
    body = payload.body
    logger.info("Acking the following headers: %s, and body: %s", headers, body)

    payload.ack()
    logger.info("Message has been removed!")


def callback_send_to_another_destination(payload: Payload, target_destination: str):
    """
    Callback used for moving messages from one destination to another.
    """
    logger.info(f"Message received!")

    headers = payload.headers
    body = payload.body

    logger.info(f"Configured headers: {headers}")
    logger.info(f"Configured body: {body}")
    logger.info("Sending to target destination...")
    publisher_name_to_move = f"{publisher_name}-{uuid.uuid4()}"

    with build_publisher(publisher_name_to_move).auto_open_close_connection() as publisher:
        with publisher.do_inside_transaction():
            # Remove the message-id header in the SEND frame since in RabbitMQ we cannot
            # set it: https://www.rabbitmq.com/stomp.html#pear.hpos
            remove_key_from_dict(headers, "message-id")
            publisher.send(body, target_destination, headers)
            payload.ack()

    logger.info("The messages has been moved!")
