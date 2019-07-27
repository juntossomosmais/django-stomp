import logging
import uuid
from time import sleep
from typing import Optional

from django.conf import settings
from django.utils.module_loading import import_string
from django_stomp.builder import build_listener
from django_stomp.helpers import eval_str_as_boolean
from django_stomp.services.consumer import Listener
from django_stomp.services.consumer import Payload
from request_id_django_log import local_threading

logger = logging.getLogger("django_stomp")

wait_to_connect = int(getattr(settings, "STOMP_WAIT_TO_CONNECT", 10))
durable_topic_subscription = eval_str_as_boolean(getattr(settings, "STOMP_DURABLE_TOPIC_SUBSCRIPTION", False))
listener_client_id = getattr(settings, "STOMP_LISTENER_CLIENT_ID", None)
if not durable_topic_subscription:
    if listener_client_id:
        listener_client_id = f"{listener_client_id}-{uuid.uuid4().hex}"


def start_processing(destination_name: str, callback_str: str, is_testing=False, testing_disconnect=True):

    callback_function = import_string(callback_str)

    listener = build_listener(destination_name, listener_client_id, durable_topic_subscription)

    def main_logic() -> Optional[Listener]:
        try:
            logger.info("Starting listener...")

            def _callback(payload: Payload) -> None:
                local_threading.request_id = payload.headers["correlation-id"]
                try:
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
                tries += 1
            elif tries >= max_tries:
                if testing_disconnect is True:
                    testing_listener.close()
                break
            else:
                sleep(0.2)
                tries += 1
