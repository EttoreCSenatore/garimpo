from structlog.testing import capture_logs

from app.events import emit


def test_emit_uses_event_type_as_message_and_keeps_fields():
    with capture_logs() as logs:
        emit({"event_type": "garimpo.product.scraped", "id": 7, "price": "99.90"})
    assert logs == [{"event": "garimpo.product.scraped", "id": 7, "price": "99.90", "log_level": "info"}]


def test_error_events_are_logged_as_errors():
    with capture_logs() as logs:
        emit({"event_type": "garimpo.error.parse", "url": "https://x"})
    assert logs[0]["log_level"] == "error"
