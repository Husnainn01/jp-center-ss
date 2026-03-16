"""S3-compatible storage for auction images."""

import os
import hashlib
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Cloudflare R2 storage
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "https://dffe00b2c327c69b4a869d74b4e7a2a2.r2.cloudflarestorage.com")
S3_BUCKET = os.getenv("S3_BUCKET", "jpcenter")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY", "")

S3_ACCESS_KEY = S3_ACCESS_KEY.strip()
S3_SECRET_KEY = S3_SECRET_KEY.strip()

print(f"  [storage] Endpoint: {S3_ENDPOINT}")
print(f"  [storage] Bucket: {S3_BUCKET}")
print(f"  [storage] Access key: {S3_ACCESS_KEY[:10]}... ({len(S3_ACCESS_KEY)} chars)")
print(f"  [storage] Secret key: ...{S3_SECRET_KEY[-10:]} ({len(S3_SECRET_KEY)} chars)")
print(f"  [storage] Secret has +: {'+' in S3_SECRET_KEY}")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
    return _client


def upload_image(img_bytes: bytes, prefix: str, source_url: str) -> str | None:
    """Upload image bytes to S3. Returns public URL or None on failure."""
    if not S3_ACCESS_KEY or not S3_SECRET_KEY:
        return None

    try:
        filename = hashlib.md5(source_url.encode()).hexdigest() + ".jpg"
        key = f"{prefix}/{filename}"

        client = _get_client()

        # Check if already exists
        try:
            client.head_object(Bucket=S3_BUCKET, Key=key)
            return f"/s3/{key}"
        except ClientError:
            pass

        client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=img_bytes,
            ContentType="image/jpeg",
        )
        return f"/s3/{key}"
    except Exception as e:
        print(f"  [storage] Upload failed for {prefix}: {e}")
        return None
