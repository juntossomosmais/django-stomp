"""
Builder service for easily creating listeners and publishers.
"""

import logging

from stomp import connect

from django_stomp.infra.base_listener import BaseStompListener
from django_stomp.services.settings_scanner import DjangoStompSettings

logger = logging.getLogger(__name__)

# required_params = {
#     "host": stomp_server_host,
#     "port": stomp_server_port,
#     "hostStandby": getattr(settings, "STOMP_SERVER_STANDBY_HOST", None),
#     "portStandby": stomp_server_standby_port,
#     "outgoingHeartbeat": outgoing_heartbeat,
#     "incomingHeartbeat": incoming_heartbeat,
#     "subscriptionId": subscription_id,
#     "vhost": getattr(settings, "STOMP_SERVER_VHOST", None),
# }
# extra_params = {"use_ssl": eval_str_as_boolean(settings.STOMP_USE_SSL), "client_id": client_id}

# logger.info("Server details connection: %s. Extra params: %s", required_params, extra_params)

# credentials = {
#     "username": getattr(settings, "STOMP_SERVER_USER", None),
#     "password": getattr(settings, "STOMP_SERVER_PASSWORD", None),
# }


def create_listener_rabbitmq(settings: DjangoStompSettings) -> BaseStompListener:
    """
    Builds a stomp listener for RabbitMQ broker.
    """
    logger.info("Building listener for RabbitMQ...")
    hosts = [(settings.stomp_server_host, settings.stomp_server_port)]

    if settings.stomp_server_standby_host and settings.stomp_server_standby_port:
        hosts.append((settings.stomp_server_standby_host, settings.stomp_server_standby_port))

    logger.info(
        f"Use SSL? {settings.use_ssl}. Version: {settings.ssl_version}. Outgoing/Ingoing heartbeat: "
        f"{settings.outgoing_heartbeat}/{settings.incoming_heartbeat}. "
        f"Background? {settings.should_process_msg_on_background}"
    )

    if (
        settings.outgoing_heartbeat > 0
        and settings.incoming_heartbeat > 0
        and not settings.should_process_msg_on_background
    ):
        logger.warning(
            "STOMP heartbeat enabled while message processing on background is disable! "
            "This could potentially lead to a false positive heartbeat timeout!"
        )

    conn = connect.StompConnection11(
        hosts,
        use_ssl=settings.use_ssl,
        ssl_version=settings.ssl_version,
        heartbeats=(settings.outgoing_heartbeat, settings.incoming_heartbeat),
        vhost=settings.vhost,
    )
    client_id = uuid.uuid4())  # TODO: review
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


def create_listener_activemq(settings: DjangoStompSettings) -> BaseStompListener:
    """
    Builds a stomp listener for RabbitMQ broker.
    """
    return BaseStompListener("x")
