import os
import signal
import logging
from unittest import mock
from uuid import uuid4

import pytest
from pytest_django.fixtures import SettingsWrapper

from django_stomp import execution
from django_stomp.execution import start_processing
from tests.support.callbacks_for_tests import callback_move_and_ack_path
from tests.support.callbacks_for_tests import callback_with_sleep_three_seconds_with_sigterm_path
from tests.support.helpers import publish_to_destination
from tests.support.helpers import wait_for_message_in_log


def _mocked_os_kill(signal: signal.Signals) -> None:
    os.kill(os.getpid(), signal)


def mocked_sigterm(*args, **kwargs) -> None:
    _mocked_os_kill(signal.SIGTERM)


def mocked_sigquit(*args, **kwargs) -> None:
    _mocked_os_kill(signal.SIGQUIT)


def mocked_sigint(*args, **kwargs) -> None:
    _mocked_os_kill(signal.SIGINT)


@pytest.fixture
def destination() -> str:
    return f"/queue/my-test-destination-one-{uuid4()}"


@mock.patch.object(execution, "get_listener_client_id")
def test_should_gracefully_shutdown_pubsub_command_when_sigterm(
    mocked_get_listener_client_id: mock.MagicMock, destination: str
):
    mocked_get_listener_client_id.side_effect = mocked_sigterm

    start_processing(
        destination,
        callback_move_and_ack_path,
        is_testing=True,
        return_listener=True,
    )

    assert execution._gracefully_shutdown is True
    assert execution._is_processing_message is False


@mock.patch.object(execution, "get_listener_client_id")
def test_should_gracefully_shutdown_pubsub_command_when_sigquit(
    mocked_get_listener_client_id: mock.MagicMock, destination: str
):
    mocked_get_listener_client_id.side_effect = mocked_sigquit

    start_processing(
        destination,
        callback_move_and_ack_path,
        is_testing=True,
        return_listener=True,
    )

    assert execution._gracefully_shutdown is True
    assert execution._is_processing_message is False


@mock.patch.object(execution, "get_listener_client_id")
def test_should_gracefully_shutdown_pubsub_command_when_sigint(
    mocked_get_listener_client_id: mock.MagicMock, destination: str
):
    mocked_get_listener_client_id.side_effect = mocked_sigint

    start_processing(
        destination,
        callback_move_and_ack_path,
        is_testing=True,
        return_listener=True,
    )

    assert execution._gracefully_shutdown is True
    assert execution._is_processing_message is False


# @mock.patch("django_stomp.execution.should_process_msg_on_background", False)
def test_should_wait_for_message_to_process_to_gracefully_shutdown(caplog, destination: str):
    caplog.set_level(logging.DEBUG)

    header = {"correlation-id": uuid4()}
    body = {"key_one": 1}

    # publishes to destination one
    publish_to_destination(destination, body, header)

    message_consumer = start_processing(
        destination,
        callback_with_sleep_three_seconds_with_sigterm_path,
        is_testing=True,
        return_listener=True,
    )

    messages_still_being_processed_message = "Messages are still being processing, waiting..."
    gracefull_shutdown_success_message = "Gracefully shutdown successfully"
    success_message = f"{body} sucessfully processed!"
    wait_for_message_in_log(caplog, messages_still_being_processed_message, message_count_to_wait=1)
    wait_for_message_in_log(caplog, gracefull_shutdown_success_message, message_count_to_wait=1)
    wait_for_message_in_log(caplog, success_message, message_count_to_wait=1)
    message_consumer.close()

    assert caplog.messages.count(messages_still_being_processed_message) >= 3
    assert messages_still_being_processed_message in caplog.messages
    assert gracefull_shutdown_success_message in caplog.messages
    assert success_message in caplog.messages


@mock.patch.object(execution, "get_listener_client_id")
def test_should_shutdown_when_time_passes(
    mocked_get_listener_client_id: mock.MagicMock, settings: SettingsWrapper, destination: str
):
    settings.STOMP_GRACEFUL_WAIT_SECONDS = 4
