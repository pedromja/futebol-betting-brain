from discovery.quota_guard import (
    PROVIDER_API_FOOTBALL,
    clear_exhausted,
    is_exhausted,
    is_quota_error,
    mark_exhausted,
)


def test_quota_error_detection():
    assert is_quota_error("You have reached the request limit for the day")
    assert not is_quota_error("invalid key")


def test_exhausted_resets_next_clear():
    clear_exhausted(PROVIDER_API_FOOTBALL)
    assert not is_exhausted(PROVIDER_API_FOOTBALL)
    mark_exhausted(PROVIDER_API_FOOTBALL)
    assert is_exhausted(PROVIDER_API_FOOTBALL)
    clear_exhausted(PROVIDER_API_FOOTBALL)
    assert not is_exhausted(PROVIDER_API_FOOTBALL)