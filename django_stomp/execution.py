import logging
import uuid
from time import sleep

from django.conf import settings
from django.utils.module_loading import import_string
from django_stomp.builder import build_listener
from django_stomp.helpers import eval_str_as_boolean
from django_stomp.services.consumer import Payload
from request_id_django_log import local_threading

logger = logging.getLogger("django_stomp")

wait_to_connect = int(getattr(settings, "STOMP_WAIT_TO_CONNECT", 10))
durable_topic_subscription = eval_str_as_boolean(getattr(settings, "STOMP_DURABLE_TOPIC_SUBSCRIPTION", False))
listener_client_id = getattr(settings, "STOMP_LISTENER_CLIENT_ID", None)
if not durable_topic_subscription:
    listener_client_id = f"{listener_client_id}-{uuid.uuid4().hex}"


def start_processing(destination_name: str, callback_str: str, is_testing=False):

    callback_function = import_string(callback_str)

    listener = build_listener(destination_name, listener_client_id, durable_topic_subscription)

    def main_logic():
        try:
            logger.info("Starting listener...")

            def _callback(payload: Payload) -> None:
                local_threading.request_id = payload.headers["correlation-id"]
                try:
                    callback_function(payload)
                finally:
                    local_threading.request_id = None

            listener.start(_callback, wait_forever=not is_testing)
        except BaseException as e:
            logger.exception(f"A exception of type {type(e)} was captured during listener logic")
        finally:
            logger.info(f"Trying to close listener...")
            if listener.is_open():
                listener.close()
            if not is_testing:
                logger.info(f"Waiting {wait_to_connect} seconds before trying to connect again...")
                sleep(wait_to_connect)

    if not is_testing:
        while True:
            main_logic()
    else:
        main_logic()
