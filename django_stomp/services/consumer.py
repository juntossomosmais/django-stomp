import json
import logging
import ssl
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Callable
from typing import Dict
from typing import Optional

import stomp
from stomp import connect
from stomp.utils import Frame as StompFrame

from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import is_heartbeat_enabled
from django_stomp.helpers import only_destination_name
from django_stomp.settings import STOMP_PROCESS_MSG_WORKERS

logger = logging.getLogger("django_stomp")


class Acknowledgements(Enum):
    """
    See more details at:
        - https://pubsub.github.io/pubsub-specification-1.2.html#SUBSCRIBE_ack_Header
        - https://jasonrbriggs.github.io/pubsub.py/api.html#acks-and-nacks
    """

    CLIENT = "client"
    CLIENT_INDIVIDUAL = "client-individual"
    AUTO = "auto"


@dataclass(frozen=True)
class Payload:
    ack: Callable
    nack: Callable
    headers: Dict
    body: Dict


class Listener(stomp.ConnectionListener):
    def __init__(
        self,
        connection: connect.StompConnection11,
        callback: Callable,
        subscription_configuration: Dict,
        connection_configuration: Dict,
        should_process_msg_on_background: bool,
        is_testing: bool = False,
        subscription_id: Optional[str] = None,
    ) -> None:
        self._subscription_configuration = subscription_configuration
        self._connection_configuration = connection_configuration
        self._connection = connection
        self._callback = callback
        self._subscription_id = f"{subscription_id if subscription_id else str(uuid.uuid4())}-listener"
        self._listener_id = str(uuid.uuid4())
        self._is_testing = is_testing
        self._should_process_msg_on_background = should_process_msg_on_background
        self._pool_executor = self._create_new_worker_executor()

        if self._is_testing:
            from stomp.listener import TestListener

            self._test_listener = TestListener()
        else:
            self._test_listener = None

    def _create_new_worker_executor(self):
        return ThreadPoolExecutor(max_workers=STOMP_PROCESS_MSG_WORKERS, thread_name_prefix=self._subscription_id)

    def on_message(self, frame: StompFrame):
        headers, body = frame.headers, frame.body

        message_id = headers["message-id"]
        logger.debug(f"Message ID: {message_id}")
        logger.debug("Received headers: %s", headers)
        logger.debug("Received message: %s", body)

        # https://jasonrbriggs.github.io/stomp.py/api.html#acks-and-nacks
        def ack_logic():
            self._connection.ack(message_id, self._subscription_id)

        def nack_logic():
            # Requeue is used because of RabbitMQ: https://www.rabbitmq.com/stomp.html#ack-nack
            self._connection.nack(message_id, self._subscription_id, requeue=False)

        payload = Payload(ack_logic, nack_logic, headers, json.loads(body))

        if self._should_process_msg_on_background:
            self._submit_task_to_worker_pool(payload)
        else:
            self._callback(payload)

    def _submit_task_to_worker_pool(self, payload):
        try:
            self._pool_executor.submit(self._callback, payload)
        except RuntimeError:
            logger.warning("Worker pool was shutdown!")
            self._pool_executor = self._create_new_worker_executor()
            self._pool_executor.submit(self._callback, payload)

    def is_open(self):
        return self._connection.is_connected()

    def start(self, callback: Callable = None, wait_forever=True):
        logger.debug(f"Starting listener with name: {self._listener_id} and auto-generated ID: {self._subscription_id}")

        self._set_listener()

        self._callback = callback if callback else self._callback
        self._connection.connect(**self._connection_configuration)
        self._connection.subscribe(
            id=self._subscription_id,
            headers=self._connection_configuration["headers"],
            **self._subscription_configuration,
        )
        logger.debug("Connected")
        if wait_forever:
            while True:
                if not self.is_open():
                    logger.info("It is not open. Starting...")
                    self.start(self._callback, wait_forever=False)
                time.sleep(1)

    def _set_listener(self):
        if self._is_testing:
            self._connection.set_listener("TESTING", self._test_listener)
        else:
            self._connection.set_listener(self._listener_id, self)

    def close(self):
        disconnect_receipt = str(uuid.uuid4())
        self._connection.disconnect(receipt=disconnect_receipt)
        logger.debug("Disconnected")

    def shutdown_worker_pool(self):
        self._pool_executor.shutdown()

    def on_error(self, frame: StompFrame):
        logger.warning("Received ERROR frame from broker - headers: %d - body: %d", frame.headers, frame.body)


def build_listener(
    destination_name,
    should_process_msg_on_background,
    callback=None,
    ack_type=Acknowledgements.CLIENT,
    durable_topic_subscription=False,
    is_testing=False,
    routing_key=None,
    **connection_params,
) -> Listener:
    hosts, vhost = [(connection_params.get("host"), connection_params.get("port"))], connection_params.get("vhost")
    if connection_params.get("hostStandby") and connection_params.get("portStandby"):
        hosts.append((connection_params.get("hostStandby"), connection_params.get("portStandby")))
    use_ssl = connection_params.get("use_ssl", False)
    ssl_version = connection_params.get("ssl_version", ssl.PROTOCOL_TLS)
    outgoing_heartbeat = int(connection_params.get("outgoingHeartbeat", 0))
    incoming_heartbeat = int(connection_params.get("incomingHeartbeat", 0))

    logger.debug(
        f"Use SSL? {use_ssl}. Version: {ssl_version}. Outgoing/Ingoing heartbeat: {outgoing_heartbeat}/{incoming_heartbeat}. Background? {should_process_msg_on_background}"
    )

    if is_heartbeat_enabled(outgoing_heartbeat, incoming_heartbeat) and not should_process_msg_on_background:
        logger.warning(
            "STOMP heartbeat enabled while message processing on background is disable! "
            "This could potentially lead to a false positive heartbeat timeout!"
        )

    # http://stomp.github.io/stomp-specification-1.2.html#Heart-beating
    # http://jasonrbriggs.github.io/stomp.py/api.html
    conn = connect.StompConnection11(
        hosts,
        ssl_version=ssl_version,
        use_ssl=use_ssl,
        heartbeats=(outgoing_heartbeat, incoming_heartbeat),
        vhost=vhost,
    )
    client_id = connection_params.get("client_id", uuid.uuid4())
    routing_key = routing_key or destination_name
    subscription_configuration = {
        "destination": routing_key,
        "ack": ack_type.value,
        # RabbitMQ
        "x-queue-name": only_destination_name(destination_name),
        "auto-delete": "false",
        "durable": "true",
    }
    header_setup = {
        # ActiveMQ
        "client-id": f"{client_id}-listener",
        "activemq.prefetchSize": "1",
        # RabbitMQ
        "prefetch-count": "1",
        # These two parameters must be set on producer side as well, otherwise you'll get precondition_failed
        "x-dead-letter-routing-key": create_dlq_destination_from_another_destination(destination_name),
        "x-dead-letter-exchange": "",
    }

    if durable_topic_subscription is True:
        durable_subs_header = {
            # ActiveMQ
            "activemq.subscriptionName": header_setup["client-id"],
            "activemq.subcriptionName": header_setup["client-id"],
        }
        header_setup.update(durable_subs_header)
    connection_configuration = {
        "username": connection_params.get("username"),
        "passcode": connection_params.get("password"),
        "wait": True,
        "headers": header_setup,
    }
    listener = Listener(
        conn,
        callback,
        subscription_configuration,
        connection_configuration,
        is_testing=is_testing,
        subscription_id=connection_params.get("subscriptionId"),
        should_process_msg_on_background=should_process_msg_on_background,
    )
    return listener
