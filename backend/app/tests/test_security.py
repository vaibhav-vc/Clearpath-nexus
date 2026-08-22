from starlette.responses import Response

from app.api.v1.auth import DUMMY_PASSWORD_HASH, _set_web_session
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, verify_password


def test_access_token_round_trip(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key-that-is-long-enough")
    token = create_access_token("operator-id")

    assert decode_access_token(token)["sub"] == "operator-id"


def test_dummy_password_hash_is_a_valid_bcrypt_hash() -> None:
    assert verify_password("not-the-dummy-password", DUMMY_PASSWORD_HASH) is False


def test_web_session_cookie_is_http_only() -> None:
    response = Response()
    _set_web_session(response, "session-token")

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "clearpath_session=session-token" in cookie
