"""AWS S3 storage provider."""

from pathlib import Path
from typing import Optional
from uuid import uuid4

import aioboto3
from botocore.exceptions import ClientError

from src.core.services.storage import StorageProvider


class S3StorageProvider(StorageProvider):
    """AWS S3 storage provider implementation."""

    def __init__(
        self,
        bucket_name: str,
        region: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.endpoint_url = endpoint_url
        self.session = aioboto3.Session()

    def _client_kwargs(self) -> dict:
        kwargs: dict = {
            "region_name": self.region,
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
        }
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return kwargs

    async def upload_file(
        self, file_content: bytes, file_name: str, content_type: Optional[str] = None
    ) -> str:
        """Upload file to S3 and return the object key."""
        parent = Path(file_name).parent
        suffix = Path(file_name).suffix
        if str(parent) != ".":
            file_key = f"{parent}/{uuid4()}{suffix}"
        else:
            file_key = f"{uuid4()}{suffix}"
        async with self.session.client("s3", **self._client_kwargs()) as s3:  # type: ignore[attr-defined]  # aioboto3 session.client() is untyped; stubs incomplete
            upload_kwargs: dict = {
                "Bucket": self.bucket_name,
                "Key": file_key,
                "Body": file_content,
                "ServerSideEncryption": "AES256",
            }
            if content_type:
                upload_kwargs["ContentType"] = content_type
            try:
                await s3.put_object(**upload_kwargs)
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "Unknown")
                msg = e.response.get("Error", {}).get("Message", str(e))
                raise ValueError(f"Failed to upload file to S3: {code} - {msg}") from e

            try:
                await s3.head_object(Bucket=self.bucket_name, Key=file_key)
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "Unknown")
                if code == "404":
                    raise ValueError(
                        "Upload appeared to succeed but object not found in S3 bucket."
                    ) from e
                raise ValueError(
                    f"Upload completed but verification failed: {code}"
                ) from e

        return file_key

    async def get_file_url(self, file_identifier: str) -> str:
        """Return a presigned URL valid for 1 hour."""
        async with self.session.client("s3", **self._client_kwargs()) as s3:  # type: ignore[attr-defined]  # aioboto3 session.client() is untyped; stubs incomplete
            try:
                return await s3.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": self.bucket_name, "Key": file_identifier},
                    ExpiresIn=3600,
                )
            except ClientError as e:
                raise ValueError(
                    f"Failed to generate URL for {file_identifier}: {e}"
                ) from e

    async def download_file(self, file_identifier: str) -> bytes:
        """Download file from S3 and return raw bytes."""
        async with self.session.client("s3", **self._client_kwargs()) as s3:  # type: ignore[attr-defined]  # aioboto3 session.client() is untyped; stubs incomplete
            try:
                resp = await s3.get_object(Bucket=self.bucket_name, Key=file_identifier)
                return await resp["Body"].read()
            except ClientError as e:
                raise ValueError(f"Failed to download {file_identifier}: {e}") from e

    async def delete_file(self, file_identifier: str) -> bool:
        """Permanently delete an object and every version / delete-marker from S3.

        A plain delete_object on a versioned bucket only inserts a delete marker
        and leaves all prior versions in place. This method lists every version
        and delete marker for the key and removes them individually via
        delete_objects, so nothing remains in the bucket after the call.

        Returns True on success (including when the key never existed).
        Requires s3:ListBucketVersions and s3:DeleteObjectVersion in addition
        to the usual s3:DeleteObject.
        """
        async with self.session.client("s3", **self._client_kwargs()) as s3:  # type: ignore[attr-defined]  # aioboto3 session.client() is untyped; stubs incomplete
            try:
                paginator = s3.get_paginator("list_object_versions")
                to_delete: list[dict] = []
                async for page in paginator.paginate(
                    Bucket=self.bucket_name, Prefix=file_identifier
                ):
                    for v in page.get("Versions", []):
                        if v["Key"] == file_identifier:
                            to_delete.append(
                                {"Key": v["Key"], "VersionId": v["VersionId"]}
                            )
                    for m in page.get("DeleteMarkers", []):
                        if m["Key"] == file_identifier:
                            to_delete.append(
                                {"Key": m["Key"], "VersionId": m["VersionId"]}
                            )

                # delete_objects accepts up to 1000 items per call
                for i in range(0, len(to_delete), 1000):
                    await s3.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={"Objects": to_delete[i : i + 1000], "Quiet": True},
                    )

                return True
            except ClientError:
                return False
