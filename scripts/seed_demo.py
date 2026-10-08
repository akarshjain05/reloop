#!/usr/bin/env python3
"""Seed a deployed stack: demo data -> DynamoDB, and the four demo accounts -> Cognito.

  python scripts/seed_demo.py --table reloop-demo --region ap-south-1 --pool <UserPoolId>

Uses the AWS credentials in your environment (the ones you used for `sam deploy`). All data is fictional."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

DEMO_ACCOUNTS = [("demo@reloop.app", "Akarsh", "USER"), ("org@reloop.app", "Meera Campus Admin", "ORGANIZATION_ADMIN"),
                 ("collector@reloop.app", "Ravi Collector", "COLLECTOR"), ("admin@reloop.app", "Platform Admin", "ADMIN")]


def seed_cognito(pool: str, region: str, password: str) -> None:
    import boto3

    cg = boto3.client("cognito-idp", region_name=region)
    for email, name, role in DEMO_ACCOUNTS:
        try:
            cg.admin_create_user(UserPoolId=pool, Username=email, MessageAction="SUPPRESS",
                                 UserAttributes=[{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}, {"Name": "name", "Value": name}])
            created = "created"
        except cg.exceptions.UsernameExistsException:
            created = "already existed"
        cg.admin_set_user_password(UserPoolId=pool, Username=email, Password=password, Permanent=True)
        cg.admin_add_user_to_group(UserPoolId=pool, Username=email, GroupName=role)
        print(f"Cognito: {email} ({role}) {created}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", required=True, help="DynamoDB table name (stack output TableName)")
    ap.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    ap.add_argument("--pool", help="Cognito user pool id (stack output UserPoolId). Omit to skip creating demo sign-ins.")
    ap.add_argument("--password", default=os.getenv("DEMO_PASSWORD", "ReLoop#Demo1"), help="Must match the stack's DemoPassword parameter")
    ap.add_argument("--force", action="store_true", help="Write the demo data even if the table is not empty")
    a = ap.parse_args()

    from app.core.config import Settings
    from app.core.container import build_container
    from app.services.seed import seed_demo

    c = build_container(Settings(app_env="local", demo_mode=True, aws_region=a.region, dynamodb_table=a.table, store_backend="dynamodb", demo_password=a.password, seed_on_start="false"))
    print("DynamoDB:", seed_demo(c, force=a.force))
    if a.pool:
        seed_cognito(a.pool, a.region, a.password)
    print("Done. Sign in with demo@reloop.app / the demo password.")


if __name__ == "__main__":
    main()
