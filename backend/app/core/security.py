"""Authentication: a dev provider (scrypt + HS256 JWT) and an Amazon Cognito provider (same interface)."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from abc import ABC, abstractmethod

import jwt

from ..models import kinds as K
from ..repositories.base import new_id, now_iso
from .config import Settings
from .errors import AppError, bad_request, conflict, unauthorized

ROLE_PRIORITY = ("ADMIN", "ORGANIZATION_ADMIN", "COLLECTOR", "USER")


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        dk = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def public_user(u: dict) -> dict:
    return {k: u.get(k) for k in ("id", "email", "name", "role", "org_id", "building_id", "demo")}


def pick_role(groups: list[str] | None) -> str:
    for r in ROLE_PRIORITY:
        if r in (groups or []):
            return r
    return "USER"


def default_building(c, building_id: str | None) -> dict | None:
    if building_id:
        b = c.store.get(K.BUILDINGS, building_id)
        if not b:
            raise bad_request("Unknown building.", "unknown_building")
        return b
    rows = c.store.list(K.BUILDINGS)
    return rows[0] if rows else None


def create_user_doc(c, email: str, name: str, role: str, building_id: str | None, password_hash: str | None = None, demo: bool = False) -> dict:
    b = default_building(c, building_id)
    u = {"id": new_id("u"), "email": email.lower(), "name": name, "role": role, "org_id": b["org_id"] if b else None,
         "building_id": b["id"] if b else None, "created_at": now_iso(), "demo": demo}
    if password_hash:
        u["password_hash"] = password_hash
    c.store.put(K.USERS, u["id"], u)
    c.store.put(K.EMAIL_IDX, u["email"], {"user_id": u["id"]})
    return u


class AuthProvider(ABC):
    kind = "abstract"

    @abstractmethod
    def register(self, c, email: str, password: str, name: str, building_id: str | None) -> dict: ...

    @abstractmethod
    def login(self, c, email: str, password: str) -> dict: ...

    @abstractmethod
    def authenticate(self, c, token: str) -> dict: ...


class DevAuth(AuthProvider):
    kind = "dev"

    def __init__(self, s: Settings) -> None:
        if s.app_env not in ("local", "test") and s.dev_jwt_secret.startswith("dev-only"):
            raise RuntimeError("Set DEV_JWT_SECRET (or configure Cognito) before running outside local/test.")
        self.secret = s.dev_jwt_secret

    def _token(self, u: dict) -> dict:
        tok = jwt.encode({"sub": u["id"], "role": u["role"], "iss": "reloop-dev", "exp": int(time.time()) + 12 * 3600}, self.secret, algorithm="HS256")
        return {"access_token": tok, "token_type": "bearer", "user": public_user(u)}

    def register(self, c, email, password, name, building_id):
        email = email.lower()
        if c.store.get(K.EMAIL_IDX, email):
            raise conflict("An account with this email already exists.", "email_taken")
        return self._token(create_user_doc(c, email, name, "USER", building_id, hash_password(password)))

    def login(self, c, email, password):
        idx = c.store.get(K.EMAIL_IDX, email.lower())
        u = c.store.get(K.USERS, idx["user_id"]) if idx else None
        if not u or not verify_password(password, u.get("password_hash", "")):
            raise unauthorized("Incorrect email or password.")
        return self._token(u)

    def authenticate(self, c, token):
        try:
            claims = jwt.decode(token, self.secret, algorithms=["HS256"], issuer="reloop-dev")
        except jwt.PyJWTError:
            raise unauthorized("Your session has expired. Please sign in again.") from None
        u = c.store.get(K.USERS, claims["sub"])
        if not u:
            raise unauthorized()
        return u


class CognitoAuth(AuthProvider):
    """Amazon Cognito user pool. The API exchanges credentials via InitiateAuth and verifies the ID token (JWKS)."""

    kind = "cognito"

    def __init__(self, s: Settings, client=None) -> None:
        import boto3

        self.pool, self.client_id = s.cognito_user_pool_id, s.cognito_client_id
        self.cg = client or boto3.client("cognito-idp", region_name=s.aws_region)
        self.issuer = f"https://cognito-idp.{s.aws_region}.amazonaws.com/{self.pool}"
        self._jwks = None

    def _verify(self, token: str) -> dict:
        try:
            if self._jwks is None:
                self._jwks = jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True)
            key = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=self.client_id, issuer=self.issuer)
        except jwt.PyJWTError:
            raise unauthorized("Your session has expired. Please sign in again.") from None
        if claims.get("token_use") != "id":
            raise unauthorized()
        return claims

    def _email_for(self, claims: dict) -> str:
        """ID tokens carry `email` only if the app client may read it; otherwise ask the pool (needs cognito-idp:AdminGetUser)."""
        from botocore.exceptions import BotoCoreError, ClientError

        if claims.get("email"):
            return claims["email"].lower()
        try:
            u = self.cg.admin_get_user(UserPoolId=self.pool, Username=claims.get("cognito:username") or claims["sub"])
            email = {a["Name"]: a["Value"] for a in u["UserAttributes"]}.get("email")
        except (ClientError, BotoCoreError):
            email = None
        if not email:
            raise unauthorized()
        return email.lower()

    def _provision(self, c, claims: dict) -> dict:
        email = self._email_for(claims)
        role = pick_role(claims.get("cognito:groups"))
        idx = c.store.get(K.EMAIL_IDX, email)
        u = c.store.get(K.USERS, idx["user_id"]) if idx else None
        if u is None:  # first sign-in for a user created outside the app (console / seed script)
            return create_user_doc(c, email, claims.get("name") or email.split("@")[0], role, None)
        if u.get("role") != role:
            u = c.store.update(K.USERS, u["id"], role=role)
        return u

    def login(self, c, email, password):
        from botocore.exceptions import ClientError

        try:
            r = self.cg.initiate_auth(ClientId=self.client_id, AuthFlow="USER_PASSWORD_AUTH",
                                      AuthParameters={"USERNAME": email.lower(), "PASSWORD": password})
            token = r["AuthenticationResult"]["IdToken"]
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NotAuthorizedException", "UserNotFoundException"):
                raise unauthorized("Incorrect email or password.") from None
            raise AppError(503, "auth_unavailable", "Sign-in is temporarily unavailable.") from e
        except KeyError:
            raise AppError(503, "auth_unavailable", "Sign-in needs an extra step that isn't supported here.") from None
        return {"access_token": token, "token_type": "bearer", "user": public_user(self._provision(c, self._verify(token)))}

    def register(self, c, email, password, name, building_id):
        from botocore.exceptions import ClientError

        email = email.lower()
        default_building(c, building_id)  # validate early
        try:
            self.cg.admin_create_user(UserPoolId=self.pool, Username=email, MessageAction="SUPPRESS",
                                      UserAttributes=[{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}, {"Name": "name", "Value": name}])
            self.cg.admin_set_user_password(UserPoolId=self.pool, Username=email, Password=password, Permanent=True)
            self.cg.admin_add_user_to_group(UserPoolId=self.pool, Username=email, GroupName="USER")
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "UsernameExistsException":
                raise conflict("An account with this email already exists.", "email_taken") from None
            if code == "InvalidPasswordException":
                raise bad_request("Password doesn't meet the policy: 8+ characters with upper, lower, number and symbol.", "weak_password") from None
            raise AppError(503, "auth_unavailable", "Sign-up is temporarily unavailable.") from e
        if not c.store.get(K.EMAIL_IDX, email):
            create_user_doc(c, email, name, "USER", building_id)
        return self.login(c, email, password)

    def authenticate(self, c, token):
        return self._provision(c, self._verify(token))


def make_auth(s: Settings) -> AuthProvider:
    return CognitoAuth(s) if s.auth_kind == "cognito" else DevAuth(s)
