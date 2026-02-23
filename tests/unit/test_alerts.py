from __future__ import annotations

from execution.alerts import AlertEvent, AlertService


class _CaptureProvider:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, *, event: AlertEvent, subject: str, body: str) -> None:
        self.messages.append((subject, body))


def test_alert_sanitization_and_redaction_blocks_secret_keys() -> None:
    provider = _CaptureProvider()
    svc = AlertService([provider], environment="prod")

    sent = svc.send(
        AlertEvent.TRADE_OPEN,
        {
            "pair": "BTC-USD",
            "strategy": "ema",
            "direction": "BUY",
            "units": 10,
            "entry_price": 100.0,
            "sl_price": 98.0,
            "tp_price": 105.0,
            "token": "top-secret",
            "password": "bad",
        },
    )

    assert sent is True
    assert len(provider.messages) == 1
    subject, body = provider.messages[0]
    assert "[prod][TRADE_OPEN]" in subject
    assert "token" not in body.lower()
    assert "password" not in body.lower()


def test_alert_dedupe_and_truncation() -> None:
    provider = _CaptureProvider()
    svc = AlertService([provider], environment="prod", dedupe_seconds=60)

    long_pair = "EUR_USD" + ("X" * 4000)
    payload = {"pair": long_pair, "strategy": "s", "direction": "BUY", "units": 1, "entry_price": 1.1, "sl_price": 1.0, "tp_price": 1.2}
    assert svc.send(AlertEvent.TRADE_OPEN, payload) is True
    assert svc.send(AlertEvent.TRADE_OPEN, payload) is False

    _, body = provider.messages[0]
    assert "<truncated>" in body
