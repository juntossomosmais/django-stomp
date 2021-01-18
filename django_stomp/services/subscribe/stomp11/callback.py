"""
Callback wrapper for STOMP 1.1 listeners.
"""
import logging
from typing import Any
from typing import Callable

from request_id_django_log import local_threading

from django_stomp.services.stomp11.context import StompContext11
from django_stomp.services.stomp11.listener import Payload
from django_stomp.subscriptions import get_or_create_correlation_id

logger = logging.getLogger(__name__)


def subscription_callback_factory(
    stomp_context: StompContext11,
    execution_callback: Callable,
    param_to_callback: Any,
    is_correlation_id_required: bool,
) -> Callable[[Payload], None]:
    """
    Factory used to wrap user callbacks with some extra logic.
    """
    # closure: defined in a lexical scope where listener and other vars are defined
    def _callback_closure(payload: Payload) -> None:
        try:

            local_threading.request_id = get_or_create_correlation_id(payload.headers, is_correlation_id_required)

            if param_to_callback:
                execution_callback(payload, param_to_callback)
            else:
                execution_callback(payload)

        except Exception as e:

            logger.exception(f"A exception of type {type(e)} was captured during callback logic")
            logger.warning("Trying to do NACK explicitly sending the message to DLQ...")

            if stomp_context.stomp_connection.is_connected():
                payload.nack()
                logger.warning("Done!")
            raise e

        finally:
            local_threading.request_id = None

    return _callback_closure
