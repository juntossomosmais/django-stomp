import importlib
import json
import logging

from django.http import HttpRequest
from django.http import JsonResponse

from django_stomp.services.consumer import Payload

_logger = logging.getLogger(__name__)


def mock_ack():
    return


def mock_nack():
    return

def debug_callback_view(request: HttpRequest):
    """
    View wrapper to call pubsub logic

    Request Body:
    ```
        {
            "callback_function_path": "path.to.your.function",
            "payload_body": {
                "user_id_ref": "0c2b3b31-6b98-426b-93d1-fb4b97038e23"
            },
            "payload_headers": {
                "fake": "headers"
            }
        }
    ```
    """
    if not request.method == "POST":
        return JsonResponse({"status": "error", "detail": "Only POST method is allowed"})

    _logger.info("What I received: %s", request.body)
    request_body = json.loads(request.body)

    callback_function_path = request_body.get("callback_function_path") or None
    if not callback_function_path:
        return JsonResponse({"status": "error", "detail": "callback_function_path is required"})

    callback_function_name = callback_function_path.split(".")[-1]
    callback_module_path = ".".join(callback_function_path.split(".")[0:-1])

    payload_body = request_body.get("payload_body") or {}
    payload_headers = request_body.get("payload_headers") or {}
    fake_payload = Payload(mock_ack, mock_nack, payload_headers, payload_body)

    callback_function = importlib.import_module(callback_module_path)
    callback_function_to_call = getattr(callback_function, callback_function_name)

    try:
        callback_function_to_call(fake_payload)
    except Exception as e:
        msg = "Exception was launched inside callback %s Error %s" % (callback_function_path, e)
        _logger.warning(msg)
        return JsonResponse({"status": "warning", "detail": msg})

    return JsonResponse({"status": "OK"})
