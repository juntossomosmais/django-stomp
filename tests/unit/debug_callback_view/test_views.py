import json

from django.http import HttpRequest

from django_stomp.debug_callback_view.views import debug_callback_view
from django_stomp.debug_callback_view.views import mock_ack
from django_stomp.debug_callback_view.views import mock_nack
from django_stomp.services.consumer import Payload


def fake_callback(payload: Payload):
    return


def test_should_call_callback_command_function(mocker):
    mock_fake_callback_function = mocker.patch("tests.unit.debug_callback_view.test_views.fake_callback")

    fake_body = {"fake": "body"}
    fake_headers = {"fake": "headers"}

    mock_request = HttpRequest()
    mock_request.method = "POST"
    mock_request._body = json.dumps(
        {
            "callback_function_path": "tests.unit.debug_callback_view.test_views.fake_callback",
            "payload_body": fake_body,
            "payload_headers": fake_headers,
        }
    )
    debug_callback_view(mock_request)
    mock_fake_callback_function.assert_called_once_with(
        (
            Payload(
                ack=mock_ack,
                nack=mock_nack,
                body=fake_body,
                headers=fake_headers,
            )
        )
    )
