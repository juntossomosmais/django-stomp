import pytest

from django_stomp.exceptions import DjangoStompImproperlyConfigured
from django_stomp.settings import eval_as_int_if_provided_value_is_not_none_otherwise_none
from django_stomp.settings import eval_settings_otherwise_raise_exception


def test_should_raise_improperly_configured_when_settings_is_not_correct_configured(mocker):
    mocked_settings = mocker.patch("django_stomp.settings.django_settings")
    mocked_settings.STOMP_PROCESS_MSG_WORKERS = "abc"
    expected_exception_message = "STOMP_PROCESS_MSG_WORKERS is not valid!"

    with pytest.raises(DjangoStompImproperlyConfigured, match=expected_exception_message):
        eval_settings_otherwise_raise_exception(
            "STOMP_PROCESS_MSG_WORKERS", eval_as_int_if_provided_value_is_not_none_otherwise_none
        )

    mocked_settings.STOMP_PROCESS_MSG_WORKERS = {}
    with pytest.raises(DjangoStompImproperlyConfigured, match=expected_exception_message):
        eval_settings_otherwise_raise_exception(
            "STOMP_PROCESS_MSG_WORKERS", eval_as_int_if_provided_value_is_not_none_otherwise_none
        )

    mocked_settings.STOMP_PROCESS_MSG_WORKERS = []
    with pytest.raises(DjangoStompImproperlyConfigured, match=expected_exception_message):
        eval_settings_otherwise_raise_exception(
            "STOMP_PROCESS_MSG_WORKERS", eval_as_int_if_provided_value_is_not_none_otherwise_none
        )


def test_should_evaluate_settings_when_it_is_configured_as_expected(mocker):
    mocked_settings = mocker.patch("django_stomp.settings.django_settings")
    mocked_settings.STOMP_PROCESS_MSG_WORKERS = None

    evaluated_settings = eval_settings_otherwise_raise_exception(
        "STOMP_PROCESS_MSG_WORKERS", eval_as_int_if_provided_value_is_not_none_otherwise_none
    )
    assert evaluated_settings is None

    mocked_settings.STOMP_PROCESS_MSG_WORKERS = 123
    evaluated_settings = eval_settings_otherwise_raise_exception(
        "STOMP_PROCESS_MSG_WORKERS", eval_as_int_if_provided_value_is_not_none_otherwise_none
    )
    assert evaluated_settings == 123

    mocked_settings.STOMP_PROCESS_MSG_WORKERS = "3"
    evaluated_settings = eval_settings_otherwise_raise_exception(
        "STOMP_PROCESS_MSG_WORKERS", eval_as_int_if_provided_value_is_not_none_otherwise_none
    )
    assert evaluated_settings == 3
