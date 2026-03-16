"""S3-compatible storage for auction images."""

import os
import hashlib
import boto3
from botocore.exceptions import ClientError

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "https://t3.storageapi.dev")
S3_BUCKET = os.getenv("S3_BUCKET", "durable-briefcase-4cwl3t7")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")

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
        )
    return _client


def upload_image(img_bytes: bytes, prefix: str, source_url: str) -> str | None:
    """Upload image bytes to S3. Returns public URL or None on failure.

    Args:
        img_bytes: Raw image bytes
        prefix: Folder prefix (e.g. 'ninja-images', 'taa-images')
        source_url: Original URL (used to generate stable filename via hash)
    """
    if not S3_ACCESS_KEY or not S3_SECRET_KEY:
        return None

    try:
        filename = hashlib.md5(source_url.encode()).hexdigest() + ".jpg"
        key = f"{prefix}/{filename}"

        client = _get_client()

        # Check if already exists
        try:
            client.head_object(Bucket=S3_BUCKET, Key=key)
            return f"{S3_ENDPOINT}/{S3_BUCKET}/{key}"
        except ClientError:
            pass

        client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=img_bytes,
            ContentType="image/jpeg",
        )
        return f"{S3_ENDPOINT}/{S3_BUCKET}/{key}"
    except Exception as e:
        print(f"  [storage] Upload failed for {prefix}: {e}")
        return None
