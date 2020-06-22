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
    headers = {
        "eventType": "sentPurchaseReceipt",
        "another": "header",
        "x-dead-letter-exchange": "",
        "tshoot-destination": "/queue/wrrrrong-again",
        "x-dead-letter-routing-key": "DLQ.wrong-really-wrong...",  # queue name should define this
    }

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
    queue = "/queue/some-destination"

    # no correlation-id supplied here
    raw_headers = {
        "subscription": "77625173-42b5-4c62-9c24-1fc4a4668dcc-listener",
        "destination": "/queue/some-destination",
        "message-id": "T_77625173-42b5-4c62-9c24-1fc4a4668dcc-listener@@session-jSfP4eyH59eKxHaZDv59Cg@@2",
        "redelivered": "false",
        "x-dead-letter-routing-key": "DLQ.wrong-really-wrong-destination",
        "x-dead-letter-exchange": "",
        "tshoot-destination": "/queue/wrong-really-wrong-destination",
        "transaction": "11837f0b-f1c5-494f-9b2b-347c636d8ca2",
        "eventType": "someType",
        "persistent": "true",
        "content-type": "application/json;charset=utf-8",
        "content-length": "298",
    }

    expected_final_headers = {
        "persistent": "true",
        "tshoot-destination": "/queue/some-destination",
        "x-dead-letter-routing-key": "DLQ.some-destination",
        "x-dead-letter-exchange": "",
        "eventType": "someType",
        "correlation-id": current_request_id,
    }

    final_headers = publisher._build_final_headers(queue, raw_headers, persistent)

    assert final_headers == expected_final_headers


def test_should_remove_unsafe_headers():
    publisher = build_publisher("test-publisher")

    unsafe_headers = {
        "subscription": "77625173-42b5-4c62-9c24-1fc4a4668dcc-listener",
        "destination": "/queue/some-destination",
        "message-id": "T_77625173-42b5-4c62-9c24-1fc4a4668dcc-listener@@session-jSfP4eyH59eKxHaZDv59Cg@@2",
        "redelivered": "false",
        "x-dead-letter-routing-key": "DLQ.some-destination",
        "x-dead-letter-exchange": "",
        "tshoot-destination": "/queue/some-destination",
        "transaction": "11837f0b-f1c5-494f-9b2b-347c636d8ca2",
        "eventType": "someType",
        "correlation-id": "6e10903e13ddcde54304883e5df713a5",
        "persistent": "true",
        "content-type": "application/json;charset=utf-8",
        "content-length": "298",
    }

    final_headers = {
        "persistent": "true",
        "tshoot-destination": "/queue/some-destination",
        "x-dead-letter-routing-key": "DLQ.some-destination",
        "x-dead-letter-exchange": "",
        "eventType": "someType",
        "correlation-id": "6e10903e13ddcde54304883e5df713a5",
    }

    # this test already considers a safe tshoot-destination, x-dead-letter-routing-key as
    # this internal method is invoked after standard_headers (safe) are imposed to the unsafe_headers
    assert publisher._remove_unsafe_or_reserved_for_broker_use_headers(unsafe_headers) == final_headers


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
