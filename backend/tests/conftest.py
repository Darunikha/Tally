import os
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ["MONGODB_URL"] = "mongomock://"

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.database import mongo
from app.main import create_app

SAMPLES = Path(__file__).resolve().parents[1] / "sample_data"


@pytest.fixture
def sample():
    return lambda name: (SAMPLES / name).read_bytes()


@pytest.fixture
async def db():
    client = AsyncMongoMockClient(tz_aware=False)
    database = client["spendly_test"]
    await mongo.ensure_indexes(database)
    mongo.set_db(database)
    yield database
    mongo.set_db(None)


@pytest.fixture
async def client(db):
    app = create_app(use_lifespan=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def register(client, email="demo@example.com", password="secret123", name="Demo"):
    r = await client.post("/api/auth/register", json={"email": email, "password": password, "full_name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def auth(client):
    return await register(client)
