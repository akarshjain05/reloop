"""Guards against drift between infrastructure/template.yaml and the application code."""
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from app.core.config import Settings
from app.models.kinds import ROLES

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "infrastructure" / "template.yaml"


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_multi_constructor("!", lambda l, s, n: {"Fn": s, "v": l.construct_scalar(n) if isinstance(n, yaml.ScalarNode) else (l.construct_sequence(n) if isinstance(n, yaml.SequenceNode) else l.construct_mapping(n))})
T = yaml.load(TEMPLATE.read_text(), Loader=_Loader)
R = T["Resources"]


def by_type(t):
    return {k: v["Properties"] for k, v in R.items() if v["Type"] == t}


def test_dynamodb_table_matches_the_repository_adapter():
    (t,) = by_type("AWS::DynamoDB::Table").values()
    assert t["BillingMode"] == "PAY_PER_REQUEST" and t["SSESpecification"]["SSEEnabled"]
    assert [k["AttributeName"] for k in t["KeySchema"]] == ["pk", "sk"]
    (g,) = t["GlobalSecondaryIndexes"]
    assert g["IndexName"] == "gsi1" and [k["AttributeName"] for k in g["KeySchema"]] == ["gsi1pk", "gsi1sk"]
    assert {a["AttributeName"] for a in t["AttributeDefinitions"]} == {"pk", "sk", "gsi1pk", "gsi1sk"}


def test_lambda_handler_path_and_environment_match_settings():
    f = R["ApiFunction"]["Properties"]
    module, attr = f["Handler"].rsplit(".", 1)
    path = ROOT / "backend" / (module.replace(".", "/") + ".py")
    assert path.is_file() and f"{attr} =" in path.read_text()
    assert f["CodeUri"] == "../backend/" and (ROOT / "backend" / "requirements.txt").is_file() and f["Runtime"] == "python3.12" and f["Timeout"] <= 29  # API Gateway limit
    env = set(f["Environment"]["Variables"])
    known = {name.upper() for name in Settings.model_fields}
    assert env <= known, f"template sets variables the app doesn't read: {env - known}"
    assert {"DYNAMODB_TABLE", "S3_BUCKET", "COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID", "BEDROCK_MODEL_ID", "BEDROCK_REGION"} <= env


def test_iam_is_least_privilege():
    stmts = [s for p in R["ApiFunction"]["Properties"]["Policies"] if "Statement" in p for s in p["Statement"]]
    actions = {a for s in stmts for a in s["Action"]}
    assert {"bedrock:InvokeModel", "cognito-idp:AdminCreateUser", "cognito-idp:AdminGetUser"} <= actions
    assert not any("*" == a or a.endswith(":*") for a in actions)
    cog = next(s for s in stmts if s["Sid"] == "ManageUsersInThisPoolOnly")
    assert cog["Resource"] == {"Fn": "GetAtt", "v": "UserPool.Arn"}  # scoped to this pool, not "*"
    assert "DynamoDBCrudPolicy" in str(R["ApiFunction"]["Properties"]["Policies"]) and "S3CrudPolicy" in str(R["ApiFunction"]["Properties"]["Policies"])


def test_cognito_client_groups_and_roles():
    (client,) = by_type("AWS::Cognito::UserPoolClient").values()
    assert "ALLOW_USER_PASSWORD_AUTH" in client["ExplicitAuthFlows"] and client["GenerateSecret"] is False and "email" in client["ReadAttributes"]
    groups = {p["GroupName"] for p in by_type("AWS::Cognito::UserPoolGroup").values()}
    assert groups == set(ROLES)  # every application role has a Cognito group


def test_buckets_are_private_and_frontend_is_served_through_cloudfront():
    buckets = by_type("AWS::S3::Bucket")
    assert len(buckets) == 2
    for b in buckets.values():
        assert all(b["PublicAccessBlockConfiguration"].values()) and b["BucketEncryption"]
    dist = next(iter(by_type("AWS::CloudFront::Distribution").values()))["DistributionConfig"]
    assert dist["DefaultCacheBehavior"]["ViewerProtocolPolicy"] == "redirect-to-https"
    assert {e["ErrorCode"] for e in dist["CustomErrorResponses"]} == {403, 404}  # SPA routing


def test_outputs_cover_deploy_and_seed_needs():
    assert {"ApiUrl", "FrontendUrl", "FrontendBucketName", "DistributionId", "UserPoolId", "UserPoolClientId", "TableName", "FunctionName", "LogGroupName"} <= set(T["Outputs"])


def test_sample_samconfig_is_valid_toml():
    import tomllib
    cfg = tomllib.loads((ROOT / "infrastructure" / "samconfig.toml.example").read_text())
    assert cfg["default"]["deploy"]["parameters"]["capabilities"] == "CAPABILITY_IAM"


@pytest.mark.skipif(not shutil.which("cfn-lint") and not (Path(__import__("sys").executable).parent / "cfn-lint").exists(), reason="cfn-lint not installed")
def test_cfn_lint_is_clean():
    exe = shutil.which("cfn-lint") or str(Path(__import__("sys").executable).parent / "cfn-lint")
    r = subprocess.run([exe, str(TEMPLATE)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
