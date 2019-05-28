import logging
import uuid
from time import sleep

from django.conf import settings
from django.db import connection
from django.db import connections
from django.utils.module_loading import import_string
from django_stomp.services import consumer
from django_stomp.services.consumer import Payload
from request_id_django_log import local_threading

logger = logging.getLogger(__name__)

listener_id = getattr(settings, "STOMP_LISTENER_CLIENT_ID", None)
if not listener_id:
    listener_id = getattr(settings, "LISTENER_CLIENT_ID", None)

listener_id = listener_id if listener_id else ""

listener_client_id = f"{listener_id}-{uuid.uuid4().hex}-listener"


connection_params = {
    "use_ssl": getattr(settings, "STOMP_USE_SSL", None),
    "host": settings.STOMP_SERVER_HOST,
    "port": int(settings.STOMP_SERVER_PORT),
    "username": getattr(settings, "STOMP_SERVER_USER", None),
    "password": getattr(settings, "STOMP_SERVER_PASSWORD", None),
    "client_id": listener_client_id,
}


def make_sure_database_is_usable() -> None:
    """
    https://github.com/speedocjx/db_platform/blob/e626a12edf8aceb299686fe19377cd6ff331b530/myapp/include/inception.py#L14
    """
    if connection.connection and not connection.is_usable():
        """
        Database might be lazily connected to in django.
        When connection.connection is None means you have not connected to mysql before.        
        Destroy the default mysql connection after this line, 
        when you use ORM methods django will reconnect to the default database
        """
        del connections._connections.default


def start_processing(queue: str, callback_str: str):

    callback = import_string(callback_str)

    def _callback(payload: Payload) -> None:
        local_threading.request_id = payload.headers["correlation-id"]

        try:
            callback(payload)
        finally:
            local_threading.request_id = None

    pentagon_listener = consumer.build_listener(queue, _callback, **connection_params)

    standard_wait_seconds = 10
    while True:
        try:
            logger.info("Starting listener...")
            pentagon_listener.start()
        except BaseException as e:
            logger.exception(f"A exception of type {type(e)} was captured during listener logic")
        finally:
            logger.info(f"Trying to close listener...")
            if pentagon_listener.is_open():
                pentagon_listener.close()
            logger.info(f"Waiting {standard_wait_seconds} seconds before trying to connect again...")
            sleep(standard_wait_seconds)
