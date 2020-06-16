"""
Module with unit tests written to assert producer (publisher) scenarios.
"""
import json
from unittest import mock
from uuid import uuid4

from django.core.serializers.json import DjangoJSONEncoder
from django_stomp.builder import build_publisher


def test_should_build_final_headers_without_removing_unsafe_headers(mocker):
    # mocks
    current_request_id = uuid4()
    mocked_current_request_id = mocker.patch("django_stomp.services.producer.current_request_id")
    mocked_current_request_id.return_value = current_request_id

    publisher = build_publisher("test-publisher")
    persistent = True
    queue = "/queue/test"
    headers = {"eventType": "sentPurchaseReceipt", "another": "header"}

    expected_final_headers = {
        "another": "header",
        "correlation-id": current_request_id,
        "eventType": "sentPurchaseReceipt",
        "persistent": "true",
        "tshoot-destination": "/queue/test",
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "DLQ.test",
    }

    final_headers = publisher._build_final_headers(queue, headers, persistent)

    assert final_headers == expected_final_headers


def test_should_build_final_headers_with_removal_of_unsafe_headers(mocker):
    # mocks
    current_request_id = uuid4()
    mocked_current_request_id = mocker.patch("django_stomp.services.producer.current_request_id")
    mocked_current_request_id.return_value = current_request_id

    publisher = build_publisher("test-publisher")
    persistent = True
    queue = "/queue/test"
    headers = {"eventType": "sentPurchaseReceipt", "message-id": "remove-me-please"}  # must be removed, its internal

    expected_final_headers = {
        # "message-id": "remove-me-please",  # should have been removed!
        "correlation-id": current_request_id,
        "eventType": "sentPurchaseReceipt",
        "persistent": "true",
        "tshoot-destination": "/queue/test",
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "DLQ.test",
    }

    final_headers = publisher._build_final_headers(queue, headers, persistent)

    assert final_headers == expected_final_headers


def test_should_remove_unsafe_headers():
    publisher = build_publisher("test-publisher")

    ok_headers = {"hello": "world", "eventType": "goal"}
    unsafe_headers = {"eventType": "goal", "message-id": "remove-me-please"}

    assert publisher._remove_unsafe_or_reserved_for_broker_use_headers(ok_headers) == ok_headers
    assert publisher._remove_unsafe_or_reserved_for_broker_use_headers(unsafe_headers) == {"eventType": "goal"}


def test_should_build_send_data_for_broker():
    publisher = build_publisher("test-publisher")

    clean_headers = {"eventType": "goal"}
    queue = "/queue/test"
    body = {"points": "100.0000"}

    expected_send_data = {
        "destination": queue,
        "body": json.dumps(body, cls=DjangoJSONEncoder),
        "headers": {"eventType": "goal"},
        "content_type": "application/json;charset=utf-8",
    }

    send_data = publisher._build_send_data(queue, body, clean_headers)
    assert expected_send_data == send_data
