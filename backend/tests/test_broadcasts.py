from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.api.routes.broadcasts import (
    AudiencePayload,
    BroadcastPayload,
    BroadcastTestPayload,
)


def test_broadcast_payload_normalizes_message() -> None:
    payload = BroadcastPayload(
        message="  Новая рассылка  ",
        audience="members",
        role_codes=["artist"],
        scheduled_at=datetime.now(timezone.utc),
    )

    assert payload.message == "Новая рассылка"
    assert payload.audience == "members"


def test_broadcast_payload_rejects_empty_message() -> None:
    with pytest.raises(ValidationError):
        BroadcastPayload(message="   ")
    with pytest.raises(ValidationError):
        BroadcastTestPayload(message="\n")


def test_broadcast_payload_rejects_unknown_audience() -> None:
    with pytest.raises(ValidationError):
        AudiencePayload(audience="subscribers")


def test_broadcast_payload_requires_timezone_for_schedule() -> None:
    with pytest.raises(ValidationError):
        BroadcastPayload(
            message="Запланированное сообщение",
            scheduled_at=datetime(2026, 8, 1, 12, 0),
        )
