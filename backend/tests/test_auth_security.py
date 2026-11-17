"""Password reset, email verification, session revocation, rate limiting, consent and data export."""
import re
from datetime import timedelta

import pytest

from app.core.config import get_settings
from app.database.mongo import AUTH_TOKENS, USERS
from app.services.email import OUTBOX
from tests.conftest import register


def _token_from_last_email(kind: str) -> str:
    msg = OUTBOX[-1]
    m = re.search(rf"http://app\.test/{kind}\?token=([\w\-%]+)", msg.text)
    assert m, msg.text
    return m.group(1)


async def test_register_requires_consent_and_records_it(client, db):
    r = await client.post("/api/auth/register", json={"email": "c@x.com", "password": "secret123", "full_name": "C"})
    assert r.status_code == 422 and "Terms" in str(r.json())
    headers = await register(client, "c@x.com")
    me = (await client.get("/api/auth/me", headers=headers)).json()
    assert me["consent"]["terms_version"] == get_settings().legal_version and me["consent"]["accepted_at"]
    assert me["email_verified"] is False


async def test_email_verification_flow(client, db):
    headers = await register(client, "v@x.com")
    assert OUTBOX and OUTBOX[-1].to == "v@x.com" and "Verify" in OUTBOX[-1].subject
    token = _token_from_last_email("verify-email")
    stored = await db[AUTH_TOKENS].find_one({"purpose": "email_verify"})
    assert token not in str(stored) and len(stored["token_hash"]) == 64  # only the hash is stored

    assert (await client.post("/api/auth/verify-email", json={"token": token})).status_code == 200
    assert (await client.get("/api/auth/me", headers=headers)).json()["email_verified"] is True
    r = await client.post("/api/auth/verify-email", json={"token": token})  # single use
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_token"
    r = await client.post("/api/auth/resend-verification", headers=headers)
    assert "already verified" in r.json()["message"]


async def test_resend_verification_invalidates_old_link(client):
    headers = await register(client, "r@x.com")
    old = _token_from_last_email("verify-email")
    await client.post("/api/auth/resend-verification", headers=headers)
    new = _token_from_last_email("verify-email")
    assert old != new
    assert (await client.post("/api/auth/verify-email", json={"token": old})).status_code == 400
    assert (await client.post("/api/auth/verify-email", json={"token": new})).status_code == 200


async def test_forgot_password_does_not_reveal_accounts(client):
    await register(client, "known@x.com")
    OUTBOX.clear()
    a = await client.post("/api/auth/forgot-password", json={"email": "known@x.com"})
    b = await client.post("/api/auth/forgot-password", json={"email": "nobody@x.com"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert [m.to for m in OUTBOX] == ["known@x.com"]


async def test_password_reset_flow_revokes_sessions(client, db):
    old_session = await register(client, "p@x.com", password="oldpass123")
    await client.post("/api/auth/forgot-password", json={"email": "p@x.com"})
    token = _token_from_last_email("reset-password")

    r = await client.post("/api/auth/reset-password", json={"token": token, "new_password": "weak"})
    assert r.status_code == 422
    r = await client.post("/api/auth/reset-password", json={"token": token, "new_password": "newpass456"})
    assert r.status_code == 200
    assert OUTBOX[-1].subject == "Your Tally password was changed"

    assert (await client.get("/api/auth/me", headers=old_session)).status_code == 401  # signed out everywhere
    assert (await client.post("/api/auth/login", json={"email": "p@x.com", "password": "oldpass123"})).status_code == 401
    r = await client.post("/api/auth/login", json={"email": "p@x.com", "password": "newpass456"})
    assert r.status_code == 200 and r.json()["user"]["email_verified"] is True  # reset proves inbox ownership
    r = await client.post("/api/auth/reset-password", json={"token": token, "new_password": "again789x"})
    assert r.status_code == 400  # link is single use


async def test_expired_and_forged_reset_tokens(client, db):
    await register(client, "e@x.com")
    await client.post("/api/auth/forgot-password", json={"email": "e@x.com"})
    token = _token_from_last_email("reset-password")
    doc = await db[AUTH_TOKENS].find_one({"purpose": "password_reset"})
    await db[AUTH_TOKENS].update_one({"_id": doc["_id"]}, {"$set": {"expires_at": doc["created_at"] - timedelta(minutes=1)}})
    assert (await client.post("/api/auth/reset-password", json={"token": token, "new_password": "newpass456"})).status_code == 400
    assert (await client.post("/api/auth/reset-password", json={"token": "x" * 43, "new_password": "newpass456"})).status_code == 400
    # a verification token cannot be used as a reset token
    await register(client, "e2@x.com")
    vtoken = _token_from_last_email("verify-email")
    assert (await client.post("/api/auth/reset-password", json={"token": vtoken, "new_password": "newpass456"})).status_code == 400


async def test_logout_everywhere(client):
    headers = await register(client, "l@x.com")
    second = (await client.post("/api/auth/login", json={"email": "l@x.com", "password": "secret123"})).json()
    other = {"Authorization": f"Bearer {second['access_token']}"}
    assert (await client.post("/api/auth/logout-all", headers=headers)).status_code == 200
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
    assert (await client.get("/api/auth/me", headers=other)).status_code == 401


async def test_login_rate_limit(client):
    await register(client, "rl@x.com")
    codes = [(await client.post("/api/auth/login", json={"email": "rl@x.com", "password": "wrong999"})).status_code
             for _ in range(9)]
    assert codes[:8] == [401] * 8 and codes[8] == 429
    r = await client.post("/api/auth/login", json={"email": "rl@x.com", "password": "secret123"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert r.json()["error"]["code"] == "rate_limited"
    # a different account from the same IP is still allowed
    await register(client, "other@x.com")
    assert (await client.post("/api/auth/login", json={"email": "other@x.com", "password": "secret123"})).status_code == 200


async def test_register_and_forgot_rate_limits(client):
    codes = []
    for i in range(6):
        r = await client.post("/api/auth/register", json={"email": f"u{i}@x.com", "password": "secret123",
                                                           "full_name": "U", "accept_terms": True})
        codes.append(r.status_code)
    assert codes == [201] * 5 + [429]
    codes = [(await client.post("/api/auth/forgot-password", json={"email": "u0@x.com"})).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


async def test_rate_limit_keys_are_hashed(client, db):
    await client.post("/api/auth/login", json={"email": "secret-person@x.com", "password": "whatever1"})
    stored = await db["rate_limits"].find().to_list(None)
    assert stored and "secret-person" not in str(stored)


async def test_email_verification_can_be_required(client, sample):
    s = get_settings()
    s.require_email_verification = True
    try:
        headers = await register(client, "gate@x.com")
        r = await client.post("/api/statements/preview", headers=headers,
                              files={"file": ("h.csv", sample("hdfc_statement.csv"), "text/csv")})
        assert r.status_code == 403 and r.json()["error"]["code"] == "email_not_verified"
        await client.post("/api/auth/verify-email", json={"token": _token_from_last_email("verify-email")})
        r = await client.post("/api/statements/preview", headers=headers,
                              files={"file": ("h.csv", sample("hdfc_statement.csv"), "text/csv")})
        assert r.status_code == 201
    finally:
        s.require_email_verification = False


async def test_export_my_data(client, auth):
    await client.post("/api/settings/demo-data", headers=auth)
    r = await client.get("/api/settings/export", headers=auth)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["profile"]["email"] == "demo@example.com"
    assert "password_hash" not in r.text and "token_version" not in r.text and "fingerprint" not in r.text
    assert len(data["transactions"]) == 133 and len(data["statements"]) == 1 and data["categories"]


async def test_delete_account_removes_tokens(client, db):
    headers = await register(client, "d@x.com")
    assert await db[AUTH_TOKENS].count_documents({}) == 1
    r = await client.request("DELETE", "/api/settings/account", headers=headers, json={"password": "secret123"})
    assert r.status_code == 200
    assert await db[AUTH_TOKENS].count_documents({}) == 0 and await db[USERS].count_documents({}) == 0


@pytest.mark.parametrize("header,expected", [("203.0.113.9", "203.0.113.9"), ("1.1.1.1, 203.0.113.9", "203.0.113.9")])
def test_client_ip_behind_proxy(header, expected):
    from starlette.requests import Request
    from app.core.ratelimit import client_ip
    req = Request({"type": "http", "headers": [(b"x-forwarded-for", header.encode())], "client": ("10.0.0.1", 1)})
    s = get_settings()
    assert client_ip(req) == "10.0.0.1"  # proxy headers ignored unless trusted (spoofable)
    s.trust_proxy_headers = True
    try:
        assert client_ip(req) == expected
    finally:
        s.trust_proxy_headers = False
