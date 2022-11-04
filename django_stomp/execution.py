import logging
import signal
import uuid
from time import time
from time import sleep
from typing import Dict
from typing import Optional
from typing import Tuple

from django import db
from django.conf import settings
from django.utils.module_loading import import_string
from request_id_django_log import local_threading

from django_stomp.builder import build_listener
from django_stomp.builder import build_publisher
from django_stomp.exceptions import CorrelationIdNotProvidedException
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import eval_str_as_boolean
from django_stomp.helpers import get_listener_client_id
from django_stomp.helpers import get_subscription_destination
from django_stomp.helpers import is_destination_from_virtual_topic
from django_stomp.helpers import remove_key_from_dict
from django_stomp.services.consumer import Listener
from django_stomp.services.consumer import Payload

logger = logging.getLogger("django_stomp")

wait_to_connect = int(getattr(settings, "STOMP_WAIT_TO_CONNECT", 10))
durable_topic_subscription = eval_str_as_boolean(getattr(settings, "STOMP_DURABLE_TOPIC_SUBSCRIPTION", False))
listener_client_id = getattr(settings, "STOMP_LISTENER_CLIENT_ID", None)
is_correlation_id_required = eval_str_as_boolean(getattr(settings, "STOMP_CORRELATION_ID_REQUIRED", True))
should_process_msg_on_background = eval_str_as_boolean(getattr(settings, "STOMP_PROCESS_MSG_ON_BACKGROUND", True))
graceful_wait_seconds = getattr(settings, "STOMP_GRACEFUL_WAIT_SECONDS", 30)
publisher_name = "django-stomp-another-target"

_listener: Optional[Listener] = None
is_gracefully_shutting_down: bool = False
_is_processing_message: bool = False


def _shutdown_handler(*args: Tuple, **kwargs: Dict) -> None:
    global _listener, is_gracefully_shutting_down, _is_processing_message

    logger.info("Received %s signal... Preparing to shutdown!", signal.Signals(args[0]).name)

    start_time = time()
    while True:
        reached_time_limit = time() > start_time + graceful_wait_seconds
        if not _is_processing_message or reached_time_limit:
            if reached_time_limit:
                logger.info("Reached time limit, forcing shutdown.")

            if _listener and _listener.is_open():
                logger.info("Listener %s was found and will now shutdown", _listener)
                _listener.close()

            logger.info("Removing request_id from thread and closing old database connections")
            local_threading.request_id = None
            db.close_old_connections()

            _listener = None
            is_gracefully_shutting_down = True
            break

        logger.info("Messages are still being processing, waiting...")
        sleep(0.5)

    logger.info("Gracefully shutdown successfully")


def start_processing(
    destination_name: str,
    callback_str: str,
    is_testing=False,
    testing_disconnect=True,
    param_to_callback=None,
    return_listener=False,
    execute_workaround_to_deal_with_rabbit_mq=True,
    broker_host_to_consume_messages: Optional[str] = None,
    broker_port_to_consume_messages: Optional[int] = None,
) -> Optional[Listener]:
    global _listener, is_gracefully_shutting_down

    signal.signal(signal.SIGQUIT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    callback_function = import_string(callback_str)

    if execute_workaround_to_deal_with_rabbit_mq:
        _create_dlq_queue(destination_name)
        if is_destination_from_virtual_topic(destination_name):
            routing_key = get_subscription_destination(destination_name)
            _create_queue(destination_name, routing_key=routing_key)
            logger.info("Created/Refreshed queue to consume from topic in case of RabbitMQ...")

    client_id = get_listener_client_id(durable_topic_subscription, listener_client_id)

    _listener = listener = build_listener(
        destination_name,
        durable_topic_subscription,
        client_id=client_id,
        should_process_msg_on_background=should_process_msg_on_background,
        custom_stomp_server_host=broker_host_to_consume_messages,
        custom_stomp_server_port=broker_port_to_consume_messages,
    )

    def main_logic() -> Optional[Listener]:
        try:
            logger.debug("Starting listener...")

            def _callback(payload: Payload) -> None:
                global _is_processing_message

                try:
                    db.close_old_connections()
                    local_threading.request_id = _get_or_create_correlation_id(payload.headers)

                    _is_processing_message = True

                    if param_to_callback:
                        callback_function(payload, param_to_callback)
                    else:
                        callback_function(payload)

                    _is_processing_message = False

                except BaseException as e:
                    logger.exception(
                        f"An exception of type {type(e)} was captured during callback logic. "
                        "Trying to do NACK explicitly sending the message to DLQ..."
                    )
                    if listener.is_open():
                        payload.nack()
                        logger.warning("Done!")
                    raise e
                finally:
                    local_threading.request_id = None
                    db.close_old_connections()

            listener.start(_callback, wait_forever=is_testing is False)

            if is_testing is True:
                return listener
        except BaseException as e:
            logger.exception(f"A exception of type {type(e)} was captured during listener logic")
        finally:
            if is_testing is False:
                logger.debug("Trying to close listener...")
                if listener.is_open():
                    listener.close()
                logger.info(f"Waiting {wait_to_connect} seconds before trying to connect again...")
                sleep(wait_to_connect)

    if is_testing is False:
        while not is_gracefully_shutting_down:
            main_logic()
    else:
        max_tries = 3
        tries = 0
        testing_listener = None
        while not is_gracefully_shutting_down:
            if tries == 0:
                testing_listener = main_logic()
                if return_listener:
                    return testing_listener
                tries += 1
            elif tries >= max_tries:
                if testing_disconnect is True:
                    testing_listener.close()
                break
            else:
                sleep(0.2)
                tries += 1


def send_message_from_one_destination_to_another(
    source_destination: str,
    target_destination: str,
    is_testing: bool = False,
    testing_disconnect: bool = True,
    return_listener: bool = False,
    custom_stomp_server_host: Optional[str] = None,
    custom_stomp_server_port: Optional[int] = None,
) -> Listener:
    callback_function = "django_stomp.execution._callback_send_to_another_destination"

    return start_processing(
        source_destination,
        callback_function,
        is_testing=is_testing,
        testing_disconnect=testing_disconnect,
        param_to_callback=target_destination,
        return_listener=return_listener,
        execute_workaround_to_deal_with_rabbit_mq=False,
        broker_host_to_consume_messages=custom_stomp_server_host,
        broker_port_to_consume_messages=custom_stomp_server_port,
    )


def clean_messages_on_destination_by_acking(
    source_destination: str, is_testing: bool = False, testing_disconnect: bool = True, return_listener: bool = False
) -> Listener:
    """
    Cleans a queue by acking all messages on it (no queue purging or deleting).
    """
    ack_only_callback_path = "django_stomp.execution._callback_for_cleaning_queues"

    return start_processing(
        source_destination,
        ack_only_callback_path,
        is_testing=is_testing,
        testing_disconnect=testing_disconnect,
        return_listener=return_listener,
        execute_workaround_to_deal_with_rabbit_mq=False,
    )


def _callback_for_cleaning_queues(payload: Payload):
    """
    Callback that just acks all messages on a queue for cleaning it.
    """
    headers = payload.headers
    body = payload.body
    logger.info("Acking the following headers: %s, and body: %s", headers, body)

    payload.ack()
    logger.info("Message has been removed!")


def _callback_send_to_another_destination(payload: Payload, target_destination):
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


def _create_queue(queue_name: str, durable_topic_subscription: bool = False, routing_key: Optional[str] = None):
    client_id = get_listener_client_id(durable_topic_subscription, listener_client_id)
    listener = build_listener(queue_name, durable_topic_subscription, client_id=client_id, routing_key=routing_key)
    listener.start(lambda payload: None, wait_forever=False)
    listener.close()


def _create_dlq_queue(destination_name: str):
    dlq_destination_name = create_dlq_destination_from_another_destination(destination_name)
    _create_queue(dlq_destination_name)
    logger.info("Created/Refreshed DLQ in case of RabbitMQ...")


def _get_or_create_correlation_id(headers: dict) -> str:
    if "correlation-id" in headers:
        return headers["correlation-id"]

    if not is_correlation_id_required:
        correlation_id = uuid.uuid4()
        logger.info(f"New correlation-id was generated {correlation_id}")
        return str(correlation_id)

    raise CorrelationIdNotProvidedException(headers)
