import json
import logging
import ssl
import uuid
from contextlib import contextmanager
from typing import Callable
from typing import Dict

import tenacity
from django.core.serializers.json import DjangoJSONEncoder
from request_id_django_log.request_id import current_request_id
from stomp import Connection
from stomp.connect import StompConnection11

logger = logging.getLogger(__name__)


class Publisher:
    def __init__(self, connection: StompConnection11, connection_configuration: Dict) -> None:
        self._connection_configuration = connection_configuration
        self.connection = connection
        self._default_content_type = "application/json;charset=utf-8"

    def is_open(self):
        return self.connection.is_connected()

    def start(self):
        self.connection.start()
        self.connection.connect(**self._connection_configuration)
        logger.info("Connected")

    def close(self):
        self.connection.disconnect()
        logger.info("Disconnected")

    def send(self, body: dict, queue: str, headers=None, attempt=10):

        correlation_id = {"correlation-id": current_request_id()}
        headers = {**headers, **correlation_id} if headers else correlation_id
        headers = self._add_persistent_messaging_header(headers)

        send_params = {
            "destination": queue,
            "body": json.dumps(body, cls=DjangoJSONEncoder),
            "headers": headers,
            "content_type": self._default_content_type,
            "transaction": getattr(self, "_tmp_transaction_id", None),
        }
        send_params = {k: v for k, v in send_params.items() if v is not None}

        def _internal_send_logic():
            if not self.is_open():
                logger.info("It is not open. Starting...")
                self.start()

            self.connection.send(**send_params)

        self._retry_send(_internal_send_logic, attempt=attempt)

    @staticmethod
    def _retry_send(function: Callable, attempt=10, *args, **kwargs):
        retry_configuration = tenacity.Retrying(
            stop=tenacity.stop_after_attempt(attempt),
            wait=tenacity.wait_fixed(3) + tenacity.wait_random(0, 2),
            after=tenacity.after_log(logger, logger.level) if logger else None,
            reraise=True,
        )
        return retry_configuration(function, *args, **kwargs)

    @staticmethod
    def _add_persistent_messaging_header(headers: Dict) -> Dict:
        value = {"persistent": True}

        if headers:
            headers.update(value)
            return headers

        return value


def build_publisher(**connection_params) -> Publisher:
    logger.info("Building publisher...")
    hosts = [(connection_params.get("host"), connection_params.get("port"))]
    use_ssl = connection_params.get("use_ssl", False)
    ssl_version = connection_params.get("ssl_version", ssl.PROTOCOL_TLS)
    logger.info(f"Use SSL? {use_ssl}. Version: {ssl_version}")
    client_id = connection_params.get("client_id", uuid.uuid4())
    connection_configuration = {
        "username": connection_params.get("username"),
        "passcode": connection_params.get("password"),
        "wait": True,
        "headers": {"client-id": f"{client_id}-publisher"},
    }
    conn = Connection(hosts, ssl_version=ssl_version, use_ssl=use_ssl)
    publisher = Publisher(conn, connection_configuration)
    return publisher


@contextmanager
def auto_open_close_connection(publisher: Publisher):
    try:
        publisher.start()
        yield
    finally:
        if publisher.is_open():
            publisher.close()


@contextmanager
def do_inside_transaction(publisher: Publisher,):
    with auto_open_close_connection(publisher):
        try:
            transaction_id = publisher.connection.begin()
            setattr(publisher, "_tmp_transaction_id", transaction_id)
            yield
            publisher.connection.commit(transaction_id)
        except BaseException as e:
            logger.exception("Error inside transaction")
            publisher.connection.abort(getattr(publisher, "_tmp_transaction_id"))
            raise e
        finally:
            if hasattr(publisher, "_tmp_transaction_id"):
                delattr(publisher, "_tmp_transaction_id")
