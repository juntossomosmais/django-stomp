import logging
import uuid
from time import sleep
from typing import Optional

from django.conf import settings
from django.utils.module_loading import import_string
from django_stomp.builder import build_listener
from django_stomp.builder import build_publisher
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import eval_str_as_boolean
from django_stomp.services.consumer import Listener
from django_stomp.services.consumer import Payload
from request_id_django_log import local_threading

logger = logging.getLogger("django_stomp")

wait_to_connect = int(getattr(settings, "STOMP_WAIT_TO_CONNECT", 10))
durable_topic_subscription = eval_str_as_boolean(getattr(settings, "STOMP_DURABLE_TOPIC_SUBSCRIPTION", False))
listener_client_id = getattr(settings, "STOMP_LISTENER_CLIENT_ID", None)
publisher_name = "django-stomp-another-target"
if not durable_topic_subscription and listener_client_id:
    listener_client_id = f"{listener_client_id}-{uuid.uuid4().hex}"


def start_processing(
    destination_name: str,
    callback_str: str,
    is_testing=False,
    testing_disconnect=True,
    param_to_callback=None,
    return_listener=False,
) -> Optional[Listener]:
    callback_function = import_string(callback_str)

    _create_dlq_queue(destination_name)
    listener = build_listener(destination_name, listener_client_id, durable_topic_subscription)

    def main_logic() -> Optional[Listener]:
        try:
            logger.info("Starting listener...")

            def _callback(payload: Payload) -> None:
                local_threading.request_id = payload.headers["correlation-id"]
                try:
                    if param_to_callback:
                        callback_function(payload, param_to_callback)
                    else:
                        callback_function(payload)
                except BaseException as e:
                    logger.exception(f"A exception of type {type(e)} was captured during callback logic")
                    logger.warning("Trying to do NACK explicitly sending the message to DLQ...")
                    if listener.is_open():
                        payload.nack()
                        logger.warning("Done!")
                    raise e
                finally:
                    local_threading.request_id = None

            listener.start(_callback, wait_forever=is_testing is False)

            if is_testing is True:
                return listener
        except BaseException as e:
            logger.exception(f"A exception of type {type(e)} was captured during listener logic")
        finally:
            if is_testing is False:
                logger.info(f"Trying to close listener...")
                if listener.is_open():
                    listener.close()
                logger.info(f"Waiting {wait_to_connect} seconds before trying to connect again...")
                sleep(wait_to_connect)

    if is_testing is False:
        while True:
            main_logic()
    else:
        max_tries = 3
        tries = 0
        testing_listener = None
        while True:
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
    source_destination: str, target_destination: str, is_testing=False, testing_disconnect=True
):
    callback_function = "django_stomp.execution._callback_send_to_another_destination"
    start_processing(
        source_destination,
        callback_function,
        is_testing=is_testing,
        testing_disconnect=testing_disconnect,
        param_to_callback=target_destination,
    )


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
            publisher.send(body, target_destination, headers)
            payload.ack()

    logger.info("The messages has been moved!")


def _create_dlq_queue(destination_name):
    dlq_destination_name = create_dlq_destination_from_another_destination(destination_name)
    listener_dlq = build_listener(dlq_destination_name, listener_client_id, durable_topic_subscription)
    listener_dlq.start(lambda payload: None, wait_forever=False)
    listener_dlq.close()
