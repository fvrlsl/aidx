"""对象存储：配置了 S3 端点则走 boto3（COS/MinIO 均兼容），否则落本地目录并由 API 静态托管。"""

import os
import uuid

from app.config import settings


class Storage:
    def __init__(self) -> None:
        self.use_s3 = bool(settings.s3_endpoint)
        if self.use_s3:
            import boto3

            self.client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
            )
        else:
            os.makedirs(settings.media_dir, exist_ok=True)

    def put_bytes(self, data: bytes, ext: str, prefix: str = "misc", content_type: str = "application/octet-stream") -> str:
        key = f"{prefix}/{uuid.uuid4().hex}.{ext.lstrip('.')}"
        if self.use_s3:
            self.client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
            base = settings.s3_public_base or f"{settings.s3_endpoint}/{settings.s3_bucket}"
            return f"{base}/{key}"
        path = os.path.join(settings.media_dir, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return f"{settings.public_base_url}/media/{key}"

    def presign_upload(self, ext: str, prefix: str = "uploads", content_type: str = "image/jpeg") -> dict:
        """小程序端附件直传：S3 模式返回预签名 PUT；本地模式返回 API 的直传接口。"""
        key = f"{prefix}/{uuid.uuid4().hex}.{ext.lstrip('.')}"
        if self.use_s3:
            url = self.client.generate_presigned_url(
                "put_object",
                Params={"Bucket": settings.s3_bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=600,
            )
            base = settings.s3_public_base or f"{settings.s3_endpoint}/{settings.s3_bucket}"
            return {"method": "PUT", "upload_url": url, "file_url": f"{base}/{key}", "key": key}
        return {
            "method": "POST",
            "upload_url": f"{settings.public_base_url}/api/v1/uploads",
            "file_url": None,
            "key": key,
        }


storage = Storage()
