import os
import signal
from unittest import mock
from uuid import uuid4

import pytest

from django_stomp import execution
from django_stomp.execution import start_processing
from tests.support.callbacks_for_tests import callback_move_and_ack_path


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


@mock.patch.object(execution, "get_listener_client_id")
def test_should_gracefully_shutdown_pubsub_command_when_sigquit(
    mocked_get_listener_client_id: mock.MagicMock, destination: str
):
    ...


@mock.patch.object(execution, "get_listener_client_id")
def test_should_gracefully_shutdown_pubsub_command_when_sigint(
    mocked_get_listener_client_id: mock.MagicMock, destination: str
):
    ...


@mock.patch.object(execution, "get_listener_client_id")
def test_should_gracefully_shutdown_immediately_when_no_message_was_received(
    mocked_get_listener_client_id: mock.MagicMock, destination: str
):
    ...


@mock.patch.object(execution, "get_listener_client_id")
def test_should_wait_for_message_to_process_to_gracefully_shutdown(
    mocked_get_listener_client_id: mock.MagicMock, destination: str
):
    ...


@mock.patch.object(execution, "get_listener_client_id")
def test_should_shutdown_when_time_passes(mocked_get_listener_client_id: mock.MagicMock, destination: str):
    ...
