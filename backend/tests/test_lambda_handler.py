"""Invokes the real Lambda entry point with API Gateway HTTP API (payload v2) events."""
import base64
import importlib
import json
import sys

import pytest

from conftest import make_image


class Ctx:
    aws_request_id = "test-request-id-1234"
    function_name = "reloop-test-api"
    memory_limit_in_mb = 1024
    invoked_function_arn = "arn:aws:lambda:ap-south-1:123456789012:function:reloop-test-api"

    @staticmethod
    def get_remaining_time_in_millis():
        return 25000


def event(method, path, body=None, headers=None, b64=False):
    h = {"host": "abc123.execute-api.ap-south-1.amazonaws.com", **(headers or {})}
    return {"version": "2.0", "routeKey": "$default", "rawPath": path, "rawQueryString": "", "headers": h, "isBase64Encoded": b64, "body": body,
            "requestContext": {"accountId": "123456789012", "apiId": "abc123", "domainName": h["host"], "domainPrefix": "abc123", "requestId": "gw-req-1", "stage": "$default",
                               "time": "01/Oct/2026:10:00:00 +0000", "timeEpoch": 1790000000000, "http": {"method": method, "path": path, "protocol": "HTTP/1.1", "sourceIp": "203.0.113.9", "userAgent": "pytest"}}}


@pytest.fixture()
def handler(monkeypatch, tmp_path):
    for k, v in {"APP_ENV": "test", "LOCAL_DATA_DIR": str(tmp_path), "SUBMISSION_COOLDOWN_SECONDS": "0", "DEMO_MODE": "true"}.items():
        monkeypatch.setenv(k, v)
    from app.core.config import get_settings
    get_settings.cache_clear()
    sys.modules.pop("app.lambda_handler", None)
    mod = importlib.import_module("app.lambda_handler")
    yield mod.handler
    sys.modules.pop("app.lambda_handler", None)
    get_settings.cache_clear()


def call(h, ev):
    r = h(ev, Ctx())
    body = r["body"]
    if r.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()
    return r["statusCode"], (json.loads(body) if body else None), r.get("headers", {})


def test_lambda_serves_the_fastapi_app(handler):
    code, body, _ = call(handler, event("GET", "/health"))
    assert code == 200 and body["status"] == "ok"
    code, body, hdrs = call(handler, event("POST", "/auth/login", json.dumps({"email": "demo@reloop.app", "password": "wrong"}), {"content-type": "application/json"}))
    assert code == 401 and body["error"]["code"] == "unauthorized" and hdrs["x-content-type-options"] == "nosniff"
    code, body, _ = call(handler, event("GET", "/nope"))
    assert code == 404 and body["error"]["message"]


def test_photo_upload_through_api_gateway_event_reaches_the_ai_flow_with_lambda_request_id(handler):
    code, login, _ = call(handler, event("POST", "/auth/login", json.dumps({"email": "demo@reloop.app", "password": "ReLoop#Demo1"}), {"content-type": "application/json"}))
    assert code == 200
    boundary = "----reloopboundary"
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="laptop.jpg"\r\nContent-Type: image/jpeg\r\n\r\n').encode() + make_image(77) + f"\r\n--{boundary}--\r\n".encode()
    ev = event("POST", "/waste/analyze", base64.b64encode(body).decode(), {"content-type": f"multipart/form-data; boundary={boundary}", "authorization": f"Bearer {login['access_token']}"}, b64=True)
    code, res, _ = call(handler, ev)
    assert code == 200, res
    sub = res["submission"]
    assert sub["item"]["item_type"] == "laptop" and sub["estimate"]["summary"]["points"] > 0
    assert sub["aws"]["lambda_request_id"] == "test-request-id-1234"  # what the in-app "Under the hood" panel shows
    code, st, _ = call(handler, event("GET", "/system/status"))
    assert code == 200 and st["runtime"]["store"] == "memory"  # this test runs locally: no AWS resources configured
