from app.api.routes.applications import (
    create_file_preview_token,
    verify_file_preview_token,
)


def test_file_preview_token_is_scoped_and_valid_before_expiration():
    token = create_file_preview_token(12, 34, expires_at=2_000)

    assert verify_file_preview_token(token, 12, 34, now=1_999)
    assert not verify_file_preview_token(token, 12, 35, now=1_999)
    assert not verify_file_preview_token(token, 13, 34, now=1_999)


def test_file_preview_token_expires_and_rejects_invalid_values():
    token = create_file_preview_token(12, 34, expires_at=2_000)

    assert not verify_file_preview_token(token, 12, 34, now=2_001)
    assert not verify_file_preview_token("invalid", 12, 34, now=1_999)
    assert not verify_file_preview_token(f"{token}changed", 12, 34, now=1_999)
