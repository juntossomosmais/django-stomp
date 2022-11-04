import json
import logging
import ssl
import uuid
from contextlib import contextmanager
from typing import Dict
from typing import Optional

from django.core.serializers.json import DjangoJSONEncoder
from request_id_django_log.request_id import current_request_id
from request_id_django_log.settings import NO_REQUEST_ID
from stomp import Connection
from stomp.connect import StompConnection11

from django_stomp.helpers import clean_dict_with_falsy_or_strange_values
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import retry
from django_stomp.helpers import slow_down

logger = logging.getLogger("django_stomp")


class Publisher:
    """
    Class used to publish messages to brokers using the STOMP protocol. Some headers are removed
    if they are in the send() method as they cause unexpected behavior/errors.

    Such headers are defined in the UNSAFE_OR_RESERVED_BROKER_HEADERS_FOR_REMOVAL class variable which is used
    for sanitizing the user-supplied headers.
    """

    UNSAFE_OR_RESERVED_BROKER_HEADERS_FOR_REMOVAL = [
        # RabbitMQ unsafe headers
        "message-id",
        "transaction",
        "redelivered",
        "subscription",
        # Unsafe in a way that only django-stomp/broker should create
        "destination",
        "content-length",
        "content-type",
    ]

    def __init__(self, connection: StompConnection11, connection_configuration: Dict) -> None:
        self._connection_configuration = connection_configuration
        self.connection = connection
        self._default_content_type = "application/json;charset=utf-8"

    def is_open(self):
        return self.connection.is_connected()

    @slow_down
    def start(self):
        self.connection.connect(**self._connection_configuration)
        logger.debug("Connected")

    def close(self):
        disconnect_receipt = str(uuid.uuid4())
        self.connection.disconnect(receipt=disconnect_receipt)
        logger.debug("Disconnected")

    def start_if_not_open(self):
        if not self.is_open():
            logger.info("It is not open. Starting...")
            self.start()

    def send(self, body: dict, queue: str, headers=None, persistent=True, attempt=10):
        """
        Builds the final message headers/body and sends to the broker with the STOMP protocol. Attempt retries
        are ignored if the publisher is currently being used in a transaction in order to avoid already closed
        transactions errors due to the STOMP protocol behavior.
        """
        headers = self._build_final_headers(queue, headers, persistent)
        send_data = self._build_send_data(queue, body, headers)

        if self._is_publisher_in_transaction():
            self._send_to_broker_without_retry_attempts(send_data)
        else:
            self._send_to_broker(send_data, how_many_attempts=attempt)

    def _build_final_headers(self, queue: str, headers: Optional[Dict], persistent: bool) -> Dict:
        """
        Builds the message final headers. Removes unsafe or broker-reserved headers.
        Standard headers values override headers values to reduce possible errors.
        """
        if headers is None:
            headers = {}

        standard_headers = {
            "correlation-id": self._get_correlation_id(headers),
            "tshoot-destination": queue,
            # RabbitMQ
            # These two parameters must be set on consumer side as well, otherwise you'll get precondition_failed
            "x-dead-letter-routing-key": create_dlq_destination_from_another_destination(queue),
            "x-dead-letter-exchange": "",
        }

        # safety: standard_headers must override headers values, so order MATTERS here!
        mixed_headers = {**headers, **standard_headers}

        if persistent:
            self._add_persistent_messaging_header(mixed_headers)

        final_headers = self._remove_unsafe_or_reserved_for_broker_use_headers(mixed_headers)
        return final_headers

    def _get_correlation_id(self, headers: Optional[Dict]) -> str:
        """
        Gets the correlation id for the message. If 'correlation-id' is in the headers, this value is used.
        Otherwise, the value of current_request_id() is returned or a new one is generated as a last resort.
        """
        if headers and "correlation-id" in headers:
            return headers["correlation-id"]

        correlation_id = current_request_id() if current_request_id() != NO_REQUEST_ID else uuid.uuid4()
        return correlation_id

    def _remove_unsafe_or_reserved_for_broker_use_headers(self, headers: Dict) -> Dict:
        """
        Removes headers that are used internally by the brokers or that might cause unexpected behaviors (unsafe).
        """
        clean_headers = {
            key: headers[key] for key in headers if key not in self.UNSAFE_OR_RESERVED_BROKER_HEADERS_FOR_REMOVAL
        }

        return clean_headers

    def _build_send_data(self, queue: str, body: Dict, headers: Dict) -> Dict:
        """
        Builds the final data shape required to send messages using the STOMP protocol.
        """
        send_data = {
            "destination": queue,
            "body": json.dumps(body, cls=DjangoJSONEncoder),
            "headers": headers,
            "content_type": self._default_content_type,
            "transaction": getattr(self, "_tmp_transaction_id", None),
        }

        send_data = clean_dict_with_falsy_or_strange_values(send_data)
        return send_data

    def _send_to_broker(self, send_data: Dict, how_many_attempts: int) -> None:
        """
        Sends the actual data to the broker using the STOMP protocol with some retry attempts if
        a connection problem occurs.
        """

        def _internal_send_logic():
            self.start_if_not_open()
            self.connection.send(**send_data)

        retry(_internal_send_logic, attempt=how_many_attempts)

    def _send_to_broker_without_retry_attempts(self, send_data: Dict) -> None:
        """
        Sends the actual data to the broker using the STOMP protocol WITHOUT any retry attempts as reconnecting to the broker
        while a transaction was previously created will lead to 'bad transaction' errors because STOMP 1.1 protocol closes any
        transactions if the producer had TCP connection problems or sends a DISCONNECT frame.

        Hence, when a producer sends a BEGIN frame, all subsequent SEND frames (messages) must always use the SAME connection that
        was used to start the transaction.

        -> STOMP 1.1 specification: https://stomp.github.io/stomp-specification-1.1.html#BEGIN
        """
        self.connection.send(**send_data)  # bare sending without retries

    def _is_publisher_in_transaction(self) -> bool:
        """
        Checks if the publisher is currently being used in a transaction.
        """
        return hasattr(self, "_tmp_transaction_id")  # attribute set by do_inside_transaction contextmanager

    @staticmethod
    def _add_persistent_messaging_header(headers: Dict) -> Dict:
        value = {"persistent": "true"}

        if headers:
            headers.update(value)
            return headers

        return value

    @contextmanager
    def auto_open_close_connection(self):
        try:
            self.start_if_not_open()
            yield self
        finally:
            if self.is_open():
                self.close()

    @contextmanager
    def do_inside_transaction(self):
        try:
            self.start_if_not_open()
            transaction_id = self.connection.begin()
            logger.debug("Created transaction ID: %s", transaction_id)
            setattr(self, "_tmp_transaction_id", transaction_id)
            yield self
            self.connection.commit(transaction_id)
        except BaseException as e:
            logger.exception("Error inside transaction")
            if hasattr(self, "_tmp_transaction_id"):
                self.connection.abort(getattr(self, "_tmp_transaction_id"))
            raise e
        finally:
            if hasattr(self, "_tmp_transaction_id"):
                delattr(self, "_tmp_transaction_id")


def build_publisher(**connection_params) -> Publisher:
    hosts, vhost = [(connection_params.get("host"), connection_params.get("port"))], connection_params.get("vhost")
    if connection_params.get("hostStandby") and connection_params.get("portStandby"):
        hosts.append((connection_params.get("hostStandby"), connection_params.get("portStandby")))
    use_ssl = connection_params.get("use_ssl", False)
    ssl_version = connection_params.get("ssl_version", ssl.PROTOCOL_TLS)
    logger.debug(f"Use SSL? {use_ssl}. Version: {ssl_version}")
    client_id = connection_params.get("client_id", uuid.uuid4())
    connection_configuration = {
        "username": connection_params.get("username"),
        "passcode": connection_params.get("password"),
        "wait": True,
        "headers": {"client-id": f"{client_id}-publisher"},
    }
    conn = Connection(hosts, ssl_version=ssl_version, use_ssl=use_ssl, vhost=vhost)
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
def do_inside_transaction(publisher: Publisher):
    try:
        publisher.start_if_not_open()
        transaction_id = publisher.connection.begin()
        logger.debug("Created transaction ID: %s", transaction_id)
        setattr(publisher, "_tmp_transaction_id", transaction_id)
        yield
        publisher.connection.commit(transaction_id)
    except BaseException as e:
        logger.exception("Error inside transaction")
        if hasattr(publisher, "_tmp_transaction_id"):
            publisher.connection.abort(getattr(publisher, "_tmp_transaction_id"))
        raise e
    finally:
        if hasattr(publisher, "_tmp_transaction_id"):
            delattr(publisher, "_tmp_transaction_id")
