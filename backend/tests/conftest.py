import io
import logging
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.core.config import Settings
from app.main import create_app

logging.disable(logging.CRITICAL)  # keep test output readable; JSON logging is exercised in test_api_flow


@pytest.fixture()
def settings(tmp_path):
    return Settings(app_env="test", local_data_dir=str(tmp_path), submission_cooldown_seconds=0, demo_mode=True)


@pytest.fixture()
def app(settings):
    return create_app(settings)


@pytest.fixture()
def c(app):
    return app.state.c


@pytest.fixture()
def client(app):
    return TestClient(app)


def auth(client, email="demo@reloop.app", password="ReLoop#Demo1") -> dict:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_image(seed: int = 0, size=(640, 480)) -> bytes:
    """Deterministic synthetic JPEG; different seeds give visibly different images."""
    im = Image.new("RGB", size, ((seed * 37) % 255, (seed * 91) % 255, (seed * 53) % 255))
    d = ImageDraw.Draw(im)
    for k in range(6):
        x, y = (seed * 31 + k * 97) % 400, (seed * 17 + k * 61) % 300
        d.rectangle([x, y, x + 90 + k * 10, y + 70 + k * 8], fill=((k * 70 + seed * 13) % 255, (k * 30 + seed * 7) % 255, (200 - k * 25) % 255))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def upload(client, headers, name="laptop.jpg", seed=1, hint=None):
    data = {"hint": hint} if hint else None
    return client.post("/waste/analyze", headers=headers, files={"image": (name, make_image(seed), "image/jpeg")}, data=data)


def today() -> str:
    return date.today().isoformat()
