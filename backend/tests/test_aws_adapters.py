"""Runs the adapters — and the whole app — against moto (an AWS emulator). This is NOT a live-AWS test."""
import boto3
import jwt
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.core.config import Settings
from app.core.security import CognitoAuth
from app.main import create_app
from app.repositories.dynamo import DynamoStore
from app.services.storage import S3Storage
from conftest import auth, upload
from test_fraud_pickups import confirmed, schedule

REGION = "ap-south-1"


@pytest.fixture()
def aws(monkeypatch):
    for k, v in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_SESSION_TOKEN": "testing", "AWS_DEFAULT_REGION": REGION}.items():
        monkeypatch.setenv(k, v)
    with mock_aws():
        yield


def create_table(name="reloop-test"):
    # mirrors infrastructure/template.yaml (asserted in test_infrastructure.py)
    boto3.resource("dynamodb", region_name=REGION).create_table(
        TableName=name, BillingMode="PAY_PER_REQUEST",
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in ("pk", "sk", "gsi1pk", "gsi1sk")],
        GlobalSecondaryIndexes=[{"IndexName": "gsi1", "KeySchema": [{"AttributeName": "gsi1pk", "KeyType": "HASH"}, {"AttributeName": "gsi1sk", "KeyType": "RANGE"}], "Projection": {"ProjectionType": "ALL"}}])


def test_dynamo_store_roundtrip_owner_index_and_pagination(aws):
    create_table()
    s = DynamoStore("reloop-test", REGION)
    assert s.is_empty()
    s.put("points_ledger", "p1", {"id": "p1", "user_id": "u1", "points": 180, "meta": {"w": 1.8, "nested": [1.5, 2]}})
    got = s.get("points_ledger", "p1")
    assert got["points"] == 180 and got["meta"]["w"] == 1.8 and got["meta"]["nested"] == [1.5, 2] and not s.is_empty()
    s.put("points_ledger", "p2", {"id": "p2", "user_id": "u2", "points": 5})
    assert [r["id"] for r in s.list("points_ledger", owner="u1")] == ["p1"] and len(s.list("points_ledger")) == 2
    s.put_many([("blobs", f"b{i:04d}", {"id": f"b{i:04d}", "pad": "x" * 9000}) for i in range(180)])  # ~1.6 MB -> forces LastEvaluatedKey pagination
    assert len(s.list("blobs")) == 180
    assert s.update("points_ledger", "p1", points=200)["points"] == 200 and s.get("points_ledger", "p1")["points"] == 200
    s.delete("points_ledger", "p2")
    assert s.get("points_ledger", "p2") is None and s.get("nope", "x") is None


def test_s3_storage_put_and_signed_url(aws):
    boto3.client("s3", region_name=REGION).create_bucket(Bucket="reloop-uploads", CreateBucketConfiguration={"LocationConstraint": REGION})
    st = S3Storage("reloop-uploads", REGION)
    meta = st.put("uploads/u1/sub1.jpg", b"jpegbytes", "image/jpeg")
    assert meta == {"backend": "s3", "key": "uploads/u1/sub1.jpg", "bucket": "reloop-uploads"}
    obj = boto3.client("s3", region_name=REGION).get_object(Bucket="reloop-uploads", Key="uploads/u1/sub1.jpg")
    assert obj["Body"].read() == b"jpegbytes" and obj["ServerSideEncryption"] == "AES256"
    assert "X-Amz-Signature" in st.url("uploads/u1/sub1.jpg") and "Expires" in st.url("uploads/u1/sub1.jpg").replace("X-Amz-Expires", "Expires")


def test_s3_failure_is_reported_not_swallowed(aws):
    st = S3Storage("bucket-that-does-not-exist", REGION)
    from app.core.errors import AppError
    with pytest.raises(AppError) as e:
        st.put("k", b"x")
    assert e.value.status == 503 and "temporarily unavailable" in e.value.message


def _mini_seed(settings):
    """A handful of documents so the app runs on DynamoDB without writing the 4,800-document demo dataset."""
    from app.core.container import build_container
    from app.core.security import hash_password
    from app.services.recyclers import seed_recyclers
    c = build_container(settings)
    c.store.put("organizations", "org_t", {"id": "org_t", "name": "Test Campus (Demo)", "type": "college", "city": "Surat"})
    c.store.put("buildings", "b_hostel_a", {"id": "b_hostel_a", "org_id": "org_t", "name": "Hostel A", "neighborhood": "Ichchhanath", "members": 40, "lat": 21.1674, "lng": 72.7862})
    pw = hash_password(settings.demo_password)
    for uid, email, role in (("u_demo", "demo@reloop.app", "USER"), ("u_collector", "collector@reloop.app", "COLLECTOR")):
        c.store.put("users", uid, {"id": uid, "email": email, "name": uid, "role": role, "org_id": "org_t", "building_id": "b_hostel_a", "password_hash": pw, "demo": True})
        c.store.put("email_index", email, {"user_id": uid})
    seed_recyclers(c)


def test_whole_app_runs_on_dynamodb_and_s3(aws, tmp_path):
    create_table()
    boto3.client("s3", region_name=REGION).create_bucket(Bucket="reloop-uploads", CreateBucketConfiguration={"LocationConstraint": REGION})
    s = Settings(app_env="test", dynamodb_table="reloop-test", s3_bucket="reloop-uploads", seed_on_start="false", demo_mode=True, submission_cooldown_seconds=0, aws_region=REGION, local_data_dir=str(tmp_path))
    _mini_seed(s)
    app = create_app(s)
    cl = TestClient(app)
    st = cl.get("/system/status").json()
    assert st["on_aws"] and st["runtime"]["store"] == "dynamodb" and st["runtime"]["storage"] == "s3" and st["runtime"]["table"] == "reloop-test" and st["runtime"]["bucket"] == "reloop-uploads"
    h = auth(cl)
    r = upload(cl, h, "laptop.jpg", 3).json()["submission"]
    assert r["aws"]["storage"] == "s3" and r["aws"]["bucket"] == "reloop-uploads" and r["aws"]["store"] == "dynamodb"
    assert boto3.client("s3", region_name=REGION).head_object(Bucket="reloop-uploads", Key=r["aws"]["object_key"])["ContentLength"] > 1000
    assert "X-Amz-Signature" in cl.get(f"/waste/{r['id']}", headers=h).json()["image_url"]
    sid = confirmed(cl, h, "monitor.jpg", 4, {"condition": "damaged"})
    pid = schedule(cl, h, [sid]).json()["id"]
    before = cl.get("/dashboard", headers=h).json()["points"]["total"]
    rw = cl.post(f"/pickups/{pid}/fast-forward", headers=h).json()["rewards"]
    assert rw["points"] > 0 and cl.get("/dashboard", headers=h).json()["points"]["total"] == before + rw["points"]
    again = DynamoStore("reloop-test", REGION)  # persisted in DynamoDB, not process memory
    assert again.get("waste_submissions", sid)["status"] == "verified" and any(row["ref_id"] == sid for row in again.list("points_ledger", owner="u_demo"))


@pytest.mark.slow
def test_full_demo_seed_loads_into_dynamodb(aws, tmp_path):
    """~4,800 documents through the batch writer. Slow against an emulator: run with `pytest -m slow`."""
    create_table()
    s = Settings(app_env="test", dynamodb_table="reloop-test", seed_on_start="true", demo_mode=True, aws_region=REGION, local_data_dir=str(tmp_path))
    cl = TestClient(create_app(s))
    d = cl.get("/dashboard", headers=auth(cl)).json()
    assert d["month"]["items"] == 27 and d["building"]["score"] > 0


def test_cognito_provider_register_login_roles(aws, tmp_path, monkeypatch):
    cg = boto3.client("cognito-idp", region_name=REGION)
    pool = cg.create_user_pool(PoolName="reloop")["UserPool"]["Id"]
    cid = cg.create_user_pool_client(UserPoolId=pool, ClientName="web", ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"])["UserPoolClient"]["ClientId"]
    for g in ("USER", "COLLECTOR", "ADMIN", "ORGANIZATION_ADMIN"):
        cg.create_group(GroupName=g, UserPoolId=pool)
    # signature verification needs the pool's live JWKS endpoint; here we only skip that one network step
    monkeypatch.setattr(CognitoAuth, "_verify", lambda self, token: jwt.decode(token, options={"verify_signature": False}))
    s = Settings(app_env="test", cognito_user_pool_id=pool, cognito_client_id=cid, aws_region=REGION, demo_mode=True, submission_cooldown_seconds=0, local_data_dir=str(tmp_path))
    app = create_app(s)
    cl = TestClient(app)
    assert app.state.c.auth.kind == "cognito" and cl.get("/system/status").json()["runtime"]["auth"] == "cognito"
    body = {"email": "new.resident@example.com", "password": "Str0ng#Passw0rd", "name": "New Resident", "building_id": "b_hostel_a"}
    r = cl.post("/auth/register", json=body)
    assert r.status_code == 201 and r.json()["user"]["role"] == "USER"
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert cl.get("/auth/me", headers=h).json()["email"] == "new.resident@example.com" and cl.get("/dashboard", headers=h).status_code == 200
    assert cl.post("/auth/register", json=body).status_code == 409
    assert cl.post("/auth/login", json={"email": body["email"], "password": "Wrong#Pass123"}).status_code == 401
    assert cl.get("/admin/dashboard", headers=h).status_code == 403
    cg.admin_add_user_to_group(UserPoolId=pool, Username=body["email"], GroupName="ADMIN")  # roles come from Cognito groups
    h2 = {"Authorization": f"Bearer {cl.post('/auth/login', json={'email': body['email'], 'password': body['password']}).json()['access_token']}"}
    assert cl.get("/admin/dashboard", headers=h2).status_code == 200
