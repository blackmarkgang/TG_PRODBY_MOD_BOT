from app.services.participant_tracking import is_configured_group


def test_private_chats_are_not_tracked() -> None:
    assert not is_configured_group(123, "private")


def test_configured_group_is_tracked(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.participant_tracking.settings.telegram_group_id",
        "-100123",
    )

    assert is_configured_group(-100123, "supergroup")
    assert not is_configured_group(-100456, "supergroup")
