import re

import pytest
from pytest_mock import MockerFixture
from stomp.connect import StompConnection11

from django_stomp.helpers import retry
from django_stomp.helpers import set_ssl_connection

ssl_key_file = "ssl_key_file"
ssl_cert_file = "ssl_cert_file"
ssl_ca_certs = "ssl_ca_certs"
ssl_cert_validator = "ssl_cert_validator"
ssl_version = "version"


def test_should_log_retry_attempts_on_warning_level(caplog):
    def raise_exception():
        raise Exception("Frango depenado")

    with pytest.raises(Exception, match="Frango depenado"):
        retry(raise_exception, attempt=3)

    tenacity_logs_regex = re.compile(r"Finished call to .* after .*, this was the .* time calling it.")
    tenacity_logs = [record for record in caplog.records if tenacity_logs_regex.match(record.message)]
    assert len(tenacity_logs) == 3
    assert all([log.levelname == "WARNING" for log in tenacity_logs])


def test_should_create_a_connection_with_success_when_and_return_it(mocker: MockerFixture):
    mocked_settings = mocker.patch("django_stomp.helpers.django_settings")
    mocked_settings.STOMP_SERVER_HOST = "127.0.0.1"
    mocked_settings.STOMP_SERVER_PORT = 61613
    mocked_settings.STOMP_HOST_AND_PORTS = [(mocked_settings.STOMP_SERVER_HOST, mocked_settings.STOMP_SERVER_PORT)]
    mocked_settings.DEFAULT_SSL_VERSION = ssl_version
    mocked_settings.DEFAULT_STOMP_KEY_FILE = ssl_key_file
    mocked_settings.DEFAULT_STOMP_CERT_FILE = ssl_cert_file
    mocked_settings.DEFAULT_STOMP_CA_CERTS = ssl_ca_certs
    mocked_settings.DEFAULT_STOMP_CERT_VALIDATOR = ssl_cert_validator
    mocked_settings.DEFAULT_STOMP_SSL_VERSION = ssl_version
    conn = set_ssl_connection(StompConnection11())
    assert conn.transport._Transport__ssl_params[mocked_settings.STOMP_HOST_AND_PORTS[0]]["key_file"] == ssl_key_file
    assert conn.transport._Transport__ssl_params[mocked_settings.STOMP_HOST_AND_PORTS[0]]["cert_file"] == ssl_cert_file
    assert conn.transport._Transport__ssl_params[mocked_settings.STOMP_HOST_AND_PORTS[0]]["ca_certs"] == ssl_ca_certs
    assert (
        conn.transport._Transport__ssl_params[mocked_settings.STOMP_HOST_AND_PORTS[0]]["cert_validator"]
        == ssl_cert_validator
    )
    assert conn.transport._Transport__ssl_params[mocked_settings.STOMP_HOST_AND_PORTS[0]]["ssl_version"] == ssl_version
