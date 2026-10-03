import pytest

from app.core.config import Settings
from app.core.errors import RateLimited
from app.core.rate_limit import RateLimiter


def test_postgres_url_is_normalised_for_asyncpg() -> None:
    s = Settings(_env_file=None, database_url="postgres://u:p@host:5432/db")  # type: ignore[call-arg]
    assert s.database_url == "postgresql+asyncpg://u:p@host:5432/db"
    s = Settings(_env_file=None, database_url="postgresql://u:p@host/db")  # type: ignore[call-arg]
    assert s.database_url.startswith("postgresql+asyncpg://")


def test_cors_origins_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert Settings(_env_file=None).cors_origins == ["https://a.example", "https://b.example"]  # type: ignore[call-arg]


def test_model_for_capability() -> None:
    s = Settings(_env_file=None, model_vision="my-vision")  # type: ignore[call-arg]
    assert s.model_for("vision") == "my-vision"


def test_rate_limiter() -> None:
    limiter = RateLimiter()
    for _ in range(3):
        limiter.check("k", 3)
    with pytest.raises(RateLimited):
        limiter.check("k", 3)
    limiter.check("other", 3)
    limiter.reset()
    limiter.check("k", 3)


def test_rate_limiter_disabled_with_zero() -> None:
    limiter = RateLimiter()
    for _ in range(100):
        limiter.check("k", 0)
