from io import StringIO

import pytest
from django.core.management import CommandError
from django.core.management import call_command
from pytest_mock import MockFixture


def test_should_call_start_processing(mocker: MockFixture):
    mock_start_processing = mocker.patch("django_stomp.management.commands.pubsub.start_processing")
    fake_queue = "/queue/your-queue"
    fake_function = "your_python_module.your_function"
    out = StringIO()

    call_command("pubsub", fake_queue, fake_function, stdout=out)

    assert "Calling internal service to consume messages" in out.getvalue()
    mock_start_processing.assert_called_with(fake_queue, fake_function)


def test_should_essential_parameters_are_required(mocker: MockFixture):
    mock_start_processing = mocker.patch("django_stomp.management.commands.pubsub.start_processing")
    fake_queue = "/queue/your-queue"

    with pytest.raises(CommandError) as e:
        call_command("pubsub")

    assert e.value.args[0] == "Error: the following arguments are required: source_destination, callback_function"

    with pytest.raises(CommandError) as e:
        call_command("pubsub", fake_queue)

    assert e.value.args[0] == "Error: the following arguments are required: callback_function"

    mock_start_processing.assert_not_called()
