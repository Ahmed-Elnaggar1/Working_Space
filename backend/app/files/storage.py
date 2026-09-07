import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


class StorageError(Exception):
    pass


class S3Storage:
    def __init__(self):
        self.endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "vault-bucket")
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self._s3_client = None
        self.local_root = Path(__file__).resolve().parent.parent / ".local_storage"

    @property
    def use_local_filesystem(self) -> bool:
        return not self.endpoint_url and not self.aws_access_key and not self.aws_secret_key

    @property
    def s3_client(self):
        if self._s3_client is None:
            session_kwargs = {}
            if self.aws_access_key and self.aws_secret_key:
                session_kwargs["aws_access_key_id"] = self.aws_access_key
                session_kwargs["aws_secret_access_key"] = self.aws_secret_key
            if self.region:
                session_kwargs["region_name"] = self.region

            client_kwargs = {}
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url

            session = boto3.Session(**session_kwargs)
            self._s3_client = session.client("s3", **client_kwargs)
        return self._s3_client

    def _local_path(self, key: str) -> Path:
        normalized = key.lstrip("/")
        return self.local_root / normalized

    def upload_file(self, key: str, file_data: bytes, content_type: str = "application/octet-stream") -> str:
        """Uploads file to S3 storage. Returns the storage path/key."""
        if self.use_local_filesystem:
            local_path = self._local_path(key)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(file_data)
            return key

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_data,
                ContentType=content_type,
            )
            return key
        except Exception as e:
            raise StorageError(f"Failed to upload file to storage: {str(e)}") from e

    def download_file(self, key: str) -> bytes:
        """Downloads file from S3 storage."""
        if self.use_local_filesystem:
            local_path = self._local_path(key)
            if not local_path.exists():
                raise StorageError(f"File not found in storage: {key}")
            return local_path.read_bytes()

        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                raise StorageError(f"File not found in storage: {key}") from e
            raise StorageError(f"Failed to download file from storage: {str(e)}") from e
        except Exception as e:
            raise StorageError(f"Failed to download file from storage: {str(e)}") from e

    def delete_file(self, key: str) -> None:
        """Deletes file from S3 storage."""
        if self.use_local_filesystem:
            local_path = self._local_path(key)
            if local_path.exists():
                local_path.unlink()
            return

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
        except Exception as e:
            raise StorageError(f"Failed to delete file from storage: {str(e)}") from e


# Global storage instance
storage = S3Storage()
