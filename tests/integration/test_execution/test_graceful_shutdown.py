import logging
from time import sleep
from typing import Dict
from typing import Generator
from typing import Tuple
from typing import Union
from unittest import mock
from uuid import UUID
from uuid import uuid4

import pytest
from pytest_django.fixtures import SettingsWrapper

from django_stomp import execution
from django_stomp.execution import start_processing
from tests.support.callbacks_for_tests import callback_move_and_ack_path
from tests.support.callbacks_for_tests import callback_with_sleep_a_seconds_with_sigint_path
from tests.support.callbacks_for_tests import callback_with_sleep_a_seconds_with_sigquit_path
from tests.support.callbacks_for_tests import callback_with_sleep_a_seconds_with_sigterm_path
from tests.support.callbacks_for_tests import callback_with_sleep_three_seconds_with_sigterm_path
from tests.support.helpers import publish_to_destination
from tests.support.helpers import wait_for_message_in_log

GRACEFULL_SHUTDOWN_SUCCESS_MESSAGE = "Gracefully shutdown successfully"


@pytest.fixture
def destination() -> str:
    return f"/queue/my-test-destination-one-{uuid4()}"


@pytest.fixture
def payload() -> Tuple[Dict[str, Union[UUID, int]]]:
    return {"correlation-id": uuid4()}, {"key_one": 1}


@pytest.fixture
def setup_fixture(destination: str, payload: Tuple[Dict[str, Union[UUID, int]]]) -> Generator:
    assert execution.is_gracefully_shutting_down is False
    assert execution._is_processing_message is False

    header, body = payload

    publish_to_destination(destination, body, header)

    yield

    # Since we've modified the state from the module we've need to reset to emulate the command finishing
    execution.is_gracefully_shutting_down = False


@pytest.mark.parametrize(
    "callback_fn",
    (
        callback_with_sleep_a_seconds_with_sigint_path,
        callback_with_sleep_a_seconds_with_sigquit_path,
        callback_with_sleep_a_seconds_with_sigterm_path,
    ),
)
def test_should_gracefully_shutting_down_pubsub_command_when_signal_is_listened(
    callback_fn: str, caplog: pytest.LogCaptureFixture, setup_fixture: Generator, destination: str
):
    caplog.set_level(logging.DEBUG)

    start_processing(
        destination,
        callback_fn,
        is_testing=True,
        return_listener=True,
    )

    wait_for_message_in_log(caplog, GRACEFULL_SHUTDOWN_SUCCESS_MESSAGE, message_count_to_wait=1)

    assert GRACEFULL_SHUTDOWN_SUCCESS_MESSAGE in caplog.messages
    assert execution.is_gracefully_shutting_down is True
    assert execution._is_processing_message is False


def test_should_wait_for_message_to_process_tois_gracefully_shutting_down(
    caplog: pytest.LogCaptureFixture,
    setup_fixture: Generator,
    destination: str,
    payload: Tuple[Dict[str, Union[UUID, int]]],
):
    caplog.set_level(logging.DEBUG)

    message_consumer = start_processing(
        destination,
        callback_with_sleep_three_seconds_with_sigterm_path,
        is_testing=True,
        return_listener=True,
    )

    _, body = payload

    messages_still_being_processed_message = "Messages are still being processing, waiting..."
    success_message = f"{body} sucessfully processed!"
    wait_for_message_in_log(caplog, messages_still_being_processed_message, message_count_to_wait=1)
    wait_for_message_in_log(caplog, GRACEFULL_SHUTDOWN_SUCCESS_MESSAGE, message_count_to_wait=1)
    wait_for_message_in_log(caplog, success_message, message_count_to_wait=1)
    message_consumer.close()

    assert caplog.messages.count(messages_still_being_processed_message) >= 3
    assert messages_still_being_processed_message in caplog.messages
    assert GRACEFULL_SHUTDOWN_SUCCESS_MESSAGE in caplog.messages
    assert success_message in caplog.messages


@mock.patch("django_stomp.execution.graceful_wait_seconds", 1)
def test_should_shutdown_when_time_passes(
    caplog: pytest.LogCaptureFixture,
    setup_fixture: Generator,
    destination: str,
    payload: Tuple[Dict[str, Union[UUID, int]]],
):
    caplog.set_level(logging.DEBUG)

    message_consumer = start_processing(
        destination,
        callback_with_sleep_three_seconds_with_sigterm_path,
        is_testing=True,
        return_listener=True,
    )

    _, body = payload

    messages_still_being_processed_message = "Messages are still being processing, waiting..."
    success_message = f"{body} sucessfully processed!"
    reached_time_limit_message = "Reached time limit, forcing shutdown."
    wait_for_message_in_log(caplog, messages_still_being_processed_message, message_count_to_wait=1)
    wait_for_message_in_log(caplog, GRACEFULL_SHUTDOWN_SUCCESS_MESSAGE, message_count_to_wait=1)
    wait_for_message_in_log(caplog, success_message, message_count_to_wait=1)
    wait_for_message_in_log(caplog, reached_time_limit_message, message_count_to_wait=1)
    message_consumer.close()

    assert caplog.messages.count(messages_still_being_processed_message) >= 2
    assert messages_still_being_processed_message in caplog.messages
    assert GRACEFULL_SHUTDOWN_SUCCESS_MESSAGE in caplog.messages
    assert success_message in caplog.messages
    assert reached_time_limit_message in caplog.messages
