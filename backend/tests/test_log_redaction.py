"""رموزُ الدخول لا تُكتب في سجلّ الخادم (`app/core/log_redaction.py`، البندُ الأمنيّ ٢٠٢٦-١١-٢٦).

**يُقاس السطرُ كما يكتبه uvicorn لا كما نظنّه**: رسالةٌ بصيغةٍ ومسارٌ معاملاً — `getMessage()` هو ما يصل `docker logs`.
والقيمُ مولَّدةٌ عند التشغيل لا حرفيّة (ماسحُ الأسرار يقرأ الحرفيّات).
"""

from __future__ import annotations

import logging
import secrets

from app.core import log_redaction
from app.core.log_redaction import MASK, QuerySecretFilter, redact


def _fake() -> str:
    return secrets.token_urlsafe(32)


def _record(msg: str, args: tuple) -> logging.LogRecord:
    return logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1, msg, args, None)


def test_websocket_accepted_line_hides_the_secret_values_and_keeps_the_names():
    value, device = _fake(), _fake()
    path = f"/api/v1/ws/driver?token={value}&device_id={device}&country=JO"
    record = _record('%s - "WebSocket %s" [accepted]', ("10.0.0.7:5123", path))

    assert QuerySecretFilter().filter(record) is True
    line = record.getMessage()

    assert value not in line and device not in line
    assert f"token={MASK}" in line and f"device_id={MASK}" in line
    # **ما ليس سرّاً يبقى للتشخيص** — والمسارُ نفسُه يبقى
    assert "country=JO" in line and "/api/v1/ws/driver?" in line


def test_access_line_with_query_secret_is_redacted():
    value = _fake()
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.7:5123", "GET", f"/api/v1/ws/rider?access_token={value}", "1.1", 101), None,
    )
    QuerySecretFilter().filter(record)
    assert value not in record.getMessage()
    assert f"access_token={MASK}" in record.getMessage()


def test_a_line_without_secrets_is_untouched():
    line = '10.0.0.7:5123 - "GET /api/v1/config?country=JO&lang=ar HTTP/1.1" 200'
    assert redact(line) == line


def test_secret_already_formatted_into_the_message_is_also_redacted():
    value = _fake()
    record = _record(f"connection open /api/v1/ws/rider?presence_token={value}", ())
    QuerySecretFilter().filter(record)
    assert value not in record.getMessage()


def test_install_attaches_once_to_both_uvicorn_loggers():
    log_redaction.install()
    log_redaction.install()
    for name in log_redaction.LOGGERS:
        attached = [f for f in logging.getLogger(name).filters if isinstance(f, QuerySecretFilter)]
        assert len(attached) == 1, name


def test_importing_the_app_installs_the_filter():
    import app.main  # noqa: F401 — الاستيرادُ نفسُه هو ما يُقاس

    for name in log_redaction.LOGGERS:
        assert any(isinstance(f, QuerySecretFilter) for f in logging.getLogger(name).filters), name
