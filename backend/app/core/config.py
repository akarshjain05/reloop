"""Runtime configuration. Everything is overridable via environment variables / .env."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    demo_mode: bool = True
    app_env: str = "local"  # local | test | production
    aws_region: str = "ap-south-1"
    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = "us.amazon.nova-lite-v1:0"
    s3_bucket: str = ""
    dynamodb_table: str = ""
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""

    # Provider selection: "auto" picks AWS when the resource is configured / running in Lambda.
    ai_provider: str = "auto"  # auto | mock | bedrock
    store_backend: str = "auto"  # auto | memory | dynamodb
    storage_backend: str = "auto"  # auto | local | s3
    auth_provider: str = "auto"  # auto | dev | cognito
    use_strands: bool = True
    seed_on_start: str = "auto"  # auto | true | false

    dev_jwt_secret: str = "dev-only-insecure-secret-change-me"
    demo_password: str = "ReLoop#Demo1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_mb: int = 4  # base64 inflates by a third; Lambda's sync payload limit is 6 MB
    submission_cooldown_seconds: int = 3
    local_data_dir: str = "../.data"  # outside backend/ so `sam build` never packages local uploads

    # i18n-ready defaults (India / INR / kg)
    currency: str = "INR"
    currency_symbol: str = "₹"
    weight_unit: str = "kg"
    country: str = "IN"
    locale: str = "en-IN"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def in_lambda(self) -> bool:
        return bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

    @property
    def store_kind(self) -> str:
        if self.store_backend in ("memory", "dynamodb"):
            return self.store_backend
        return "dynamodb" if self.dynamodb_table else "memory"

    @property
    def storage_kind(self) -> str:
        if self.storage_backend in ("local", "s3"):
            return self.storage_backend
        return "s3" if self.s3_bucket else "local"

    @property
    def auth_kind(self) -> str:
        if self.auth_provider in ("dev", "cognito"):
            return self.auth_provider
        return "cognito" if (self.cognito_user_pool_id and self.cognito_client_id) else "dev"

    @property
    def ai_kind(self) -> str:
        if self.ai_provider in ("mock", "bedrock"):
            return self.ai_provider
        return "bedrock" if self.in_lambda else "mock"

    @property
    def should_seed(self) -> bool:
        v = self.seed_on_start.lower()
        if v in ("true", "1", "yes"):
            return True
        if v in ("false", "0", "no"):
            return False
        return self.store_kind == "memory" and self.demo_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
