import json

from django.http import HttpRequest

from django_stomp.debug_callback_view.views import debug_callback_view
from django_stomp.debug_callback_view.views import mock_ack
from django_stomp.debug_callback_view.views import mock_nack
from django_stomp.services.consumer import Payload

fake_callback_path = "tests.unit.debug_callback_view.test_views.fake_callback"


def fake_callback(payload: Payload):
    return


def test_should_return_error_when_method_not_is_post(mocker):
    mock_fake_callback_function = mocker.patch(fake_callback_path)

    mock_request = HttpRequest()
    mock_request.method = "GET"

    response = debug_callback_view(mock_request)

    assert response.status_code == 200
    assert response.content == b'{"status": "error", "detail": "Only POST method is allowed"}'

    mock_fake_callback_function.assert_not_called()


def test_should_return_error_when_callback_function_path_body_attribute_is_not_provided(mocker):
    mock_fake_callback_function = mocker.patch(fake_callback_path)

    mock_request = HttpRequest()
    mock_request.method = "POST"
    mock_request._body = json.dumps({})  # empty body

    response = debug_callback_view(mock_request)

    assert response.status_code == 200
    assert response.content == b'{"status": "error", "detail": "callback_function_path is required"}'

    mock_fake_callback_function.assert_not_called()


def test_should_return_warning_when_callback_function_raise_error(mocker):
    mock_fake_callback_function = mocker.patch(fake_callback_path)
    mock_fake_callback_function.side_effect = Exception(":careca:")

    fake_body = {"fake": "body"}
    fake_headers = {"fake": "headers"}

    mock_request = HttpRequest()
    mock_request.method = "POST"
    mock_request._body = json.dumps(
        {
            "callback_function_path": fake_callback_path,
            "payload_body": fake_body,
            "payload_headers": fake_headers,
        }
    )

    response = debug_callback_view(mock_request)

    assert response.status_code == 200
    assert (
        response.content == b'{"status": "warning", "detail": "Exception was launched inside callback '
        b'tests.unit.debug_callback_view.test_views.fake_callback Error :careca:"}'
    )

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
