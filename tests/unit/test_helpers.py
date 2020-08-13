import re

import pytest

from django_stomp.helpers import retry


def test_should_log_retry_attempts_on_warning_level(caplog):
    def raise_exception():
        raise Exception("Frango depenado")

    with pytest.raises(Exception, match="Frango depenado"):
        retry(raise_exception, attempt=3)

    tenacity_logs_regex = re.compile(r"Finished call to .* after .*, this was the .* time calling it.")
    tenacity_logs = [record for record in caplog.records if tenacity_logs_regex.match(record.message)]
    assert len(tenacity_logs) == 3
    assert all([log.levelname == "WARNING" for log in tenacity_logs])
