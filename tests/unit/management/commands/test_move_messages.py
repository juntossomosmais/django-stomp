from io import StringIO

import pytest
from django.core.management import CommandError
from django.core.management import call_command
from pytest_mock import MockFixture


def test_should_call_logic_to_send_one_destination_to_another(mocker):
    mock_send_message_from_one_destination_to_another = mocker.patch(
        "django_stomp.management.commands.move_messages.send_message_from_one_destination_to_another"
    )
    out = StringIO()
    fake_source = "/queue/your-source"
    fake_target = "/queue/your-target"

    call_command("move_messages", fake_source, fake_target, stdout=out)

    assert "Calling internal service to send messages to target" in out.getvalue()
    mock_send_message_from_one_destination_to_another.assert_called_with(fake_source, fake_target)


def test_should_essential_parameters_are_required(mocker: MockFixture):
    mock_send_message_from_one_destination_to_another = mocker.patch(
        "django_stomp.management.commands.move_messages.send_message_from_one_destination_to_another"
    )
    fake_source = "/queue/your-source"

    with pytest.raises(CommandError) as e:
        call_command("move_messages")

    assert e.value.args[0] == "Error: the following arguments are required: source_destination, target_destination"

    with pytest.raises(CommandError) as e:
        call_command("move_messages", fake_source)

    assert e.value.args[0] == "Error: the following arguments are required: target_destination"

    mock_send_message_from_one_destination_to_another.assert_not_called()
