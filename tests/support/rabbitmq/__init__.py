import json
import urllib.parse
from time import sleep
from typing import Generator
from typing import Optional

import requests
from requests.adapters import HTTPAdapter

from tests.support.dtos import ConsumerStatus
from tests.support.dtos import CurrentDestinationStatus
from tests.support.dtos import MessageStatus

_queues_details_request_path = "/api/queues"
_bindings_from_queue_request_path = _queues_details_request_path + "/%2F/{queue_name}/bindings"
_get_message_from_queue_request_path = _queues_details_request_path + "/%2F/{queue_name}/get"
_channels_details_request_path = "/api/channels"
_channel_details_from_channel_request_path = _channels_details_request_path + "/{channel_name}"


def current_queue_configuration(queue_name, host="localhost", port=15672) -> Optional[CurrentDestinationStatus]:
    queues = _do_request(host, port, _queues_details_request_path)
    results = list(filter(lambda v: v["name"] == queue_name, queues))
    if len(results) == 1:
        queue_details = results[0]
        if queue_details.get("message_stats"):
            message_stats = queue_details["message_stats"]
            messages_dequeued = message_stats.get("deliver_get", 0)
            messages_enqueued = message_stats["publish"]
        else:
            messages_dequeued = 0
            messages_enqueued = None

        number_of_pending_messages = queue_details["messages"]
        number_of_consumers = queue_details["consumers"]

        return CurrentDestinationStatus(
            number_of_pending_messages, number_of_consumers, messages_enqueued, messages_dequeued
        )
    return None


def current_topic_configuration(topic_name, host="localhost", port=15672) -> Optional[CurrentDestinationStatus]:
    queues = _do_request(host, port, _queues_details_request_path + "?name=&use_regex=false")
    for queue_details in queues:
        queue_name = queue_details["name"]
        bindings = _do_request(host, port, _bindings_from_queue_request_path.format(queue_name=queue_name))
        for binding in bindings:
            if binding["source"] == "amq.topic" and binding["routing_key"] == topic_name:
                message_stats = queue_details["message_stats"]
                number_of_pending_messages = queue_details["messages"]
                number_of_consumers = queue_details["consumers"]
                messages_enqueued = message_stats["publish"]
                messages_dequeued = message_stats["deliver_get"] if message_stats.get("deliver_get") else 0
                return CurrentDestinationStatus(
                    number_of_pending_messages, number_of_consumers, messages_enqueued, messages_dequeued
                )
    return None


def consumers_details(connection_id, host="localhost", port=15672) -> Generator[ConsumerStatus, None, None]:
    channels = _do_request(host, port, _channels_details_request_path)
    for channel in channels:
        channel_name = channel["connection_details"]["name"]
        channel_details = _do_request(
            host,
            port,
            _channel_details_from_channel_request_path.format(
                channel_name=urllib.parse.quote(f"{channel_name} ") + "(1)"
            ),
        )
        if channel_details.get("consumer_details"):
            for consumer in channel_details["consumer_details"]:
                if consumer["consumer_tag"] == f"T_{connection_id}":
                    yield ConsumerStatus(
                        address_to_destination_details=None,
                        destination_name=consumer["queue"]["name"],
                        session_id=None,
                        enqueues=None,
                        dequeues=None,
                        dispatched=None,
                        dispatched_queue=None,
                        prefetch=consumer["prefetch_count"],
                        max_pending=channel_details["messages_unacknowledged"],
                        exclusive=consumer["exclusive"],
                        retroactive=None,
                    )


def retrieve_message_published(destination_name, host="localhost", port=15672) -> MessageStatus:
    body = json.dumps(
        {
            "vhost": "/",
            "name": destination_name,
            "truncate": "50000",
            "ackmode": "ack_requeue_false",
            "encoding": "auto",
            "count": "1",
        }
    )
    message_details = _do_request(
        host, port, _get_message_from_queue_request_path.format(queue_name=destination_name), do_post=True, body=body
    )
    assert len(message_details) == 1
    properties = message_details[0]["properties"]

    details = json.loads(message_details[0]["payload"])
    persistent = None
    correlation_id = properties["correlation_id"]
    headers = properties.pop("headers")

    return MessageStatus(None, details, persistent, correlation_id, {**headers, **properties})


def _do_request(host, port, request_path, do_post=False, body=None):
    sleep(5)
    session = requests.Session()
    session.mount("http://", HTTPAdapter(max_retries=3))
    address, auth = f"http://{host}:{port}{request_path}", ("guest", "guest")
    with session:
        if not do_post:
            data = session.get(address, auth=auth)
        else:
            data = session.post(address, auth=auth, data=body)
    return data.json()
