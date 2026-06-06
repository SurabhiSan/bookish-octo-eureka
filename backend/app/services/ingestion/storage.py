import boto3
from botocore.exceptions import ClientError
from app.core.config import get_settings


def _get_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url or None,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
    )


async def upload_to_r2(key: str, content: bytes) -> None:
    settings = get_settings()
    import asyncio
    loop = asyncio.get_event_loop()
    client = _get_s3_client()
    await loop.run_in_executor(
        None,
        lambda: client.put_object(Bucket=settings.r2_bucket_name, Key=key, Body=content),
    )


def download_from_r2(key: str) -> bytes:
    settings = get_settings()
    client = _get_s3_client()
    response = client.get_object(Bucket=settings.r2_bucket_name, Key=key)
    return response["Body"].read()


def delete_from_r2(key: str) -> None:
    settings = get_settings()
    client = _get_s3_client()
    try:
        client.delete_object(Bucket=settings.r2_bucket_name, Key=key)
    except ClientError:
        pass
