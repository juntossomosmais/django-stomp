"""
Module with callback-related definitions used on SUBSCRIPTIONS.
"""
import logging
import uuid
from typing import Any
from typing import Callable

from request_id_django_log import local_threading

from django_stomp.builder import build_publisher
from django_stomp.helpers import remove_key_from_dict
from django_stomp.services.consumer import Payload
from django_stomp.subscriptions import get_or_create_correlation_id

publisher_name = "django-stomp-another-target"

logger = logging.getLogger(__name__)


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
