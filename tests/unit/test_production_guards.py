import pytest


def test_production_service_secret_has_no_development_fallback(monkeypatch):
    from datamind_gateway.auth import _secret

    monkeypatch.setenv("DATAMIND_ENV", "production")
    monkeypatch.delenv("DATAMIND_SERVICE_JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="DATAMIND_SERVICE_JWT_SECRET"):
        _secret("DATAMIND_SERVICE_JWT_SECRET")


def test_development_service_secret_remains_available(monkeypatch):
    from datamind_gateway.auth import _secret

    monkeypatch.setenv("DATAMIND_ENV", "development")
    monkeypatch.delenv("DATAMIND_SERVICE_JWT_SECRET", raising=False)
    assert _secret("DATAMIND_SERVICE_JWT_SECRET") == "development-only-change-me"
