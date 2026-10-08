"""Image storage: local disk for development, Amazon S3 (private bucket + signed URLs) on AWS."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ..core.config import Settings
from ..core.errors import AppError, bad_request


class ImageStorage(ABC):
    kind = "abstract"

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str = "image/jpeg") -> dict: ...

    @abstractmethod
    def url(self, key: str, expires: int = 3600) -> str: ...


class LocalStorage(ImageStorage):
    kind = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise bad_request("Invalid path.", "invalid_path")
        return p

    def put(self, key, data, content_type="image/jpeg"):
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return {"backend": "local", "key": key, "bucket": None}

    def url(self, key, expires=3600):
        return f"/media/{key}"


class S3Storage(ImageStorage):
    kind = "s3"

    def __init__(self, bucket: str, region: str, client=None) -> None:
        self.bucket = bucket
        self.client = client or boto3.client("s3", region_name=region, config=Config(signature_version="s3v4"))

    def put(self, key, data, content_type="image/jpeg"):
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type, ServerSideEncryption="AES256")
        except (ClientError, BotoCoreError) as e:
            raise AppError(503, "storage_unavailable", "Image storage is temporarily unavailable. Please try again.") from e
        return {"backend": "s3", "key": key, "bucket": self.bucket}

    def url(self, key, expires=3600):
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires)


def make_storage(s: Settings) -> ImageStorage:
    if s.storage_kind == "s3":
        return S3Storage(s.s3_bucket, s.aws_region)
    return LocalStorage(s.local_data_dir)
