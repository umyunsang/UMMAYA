# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import logging

from ummaya.ipc.stdio import _BackendSecretRedactionFilter


def test_backend_log_filter_redacts_auth_key_url_args() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP Request: %s",
        args=(
            "https://weather.example.test/api/typ01/url/kma_sfctm3.php?authKey=kma-secret&icao=RKSS",
        ),
        exc_info=None,
    )

    assert _BackendSecretRedactionFilter().filter(record) is True

    message = record.getMessage()
    assert "kma-secret" not in message
    assert "authKey=" not in message
    assert "[REDACTED_SERVICE_KEY]" in message
    assert "icao=RKSS" in message
