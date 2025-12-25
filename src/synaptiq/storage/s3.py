"""
S3 storage service for file uploads.

Supports:
- AWS S3
- MinIO (S3-compatible)
- LocalStack (for local development)
"""

import io
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import structlog

from config.settings import get_settings
from synaptiq.core.exceptions import StorageError

logger = structlog.get_logger(__name__)


class S3Store:
    """
    S3 storage client for file uploads.
    
    Files are organized by user: uploads/{user_id}/{year}/{month}/{filename}
    """

    def __init__(self):
        """Initialize S3 client."""
        self.settings = get_settings()
        self._client = None
        self._initialized = False

    def _get_client(self):
        """Lazy initialization of boto3 client."""
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError:
                raise StorageError(
                    message="boto3 is required for S3 storage. Install with: pip install boto3",
                    store_type="s3",
                    operation="init",
                )

            config = Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                connect_timeout=5,
                read_timeout=30,
            )

            client_kwargs = {
                "service_name": "s3",
                "region_name": self.settings.aws_region,
                "config": config,
            }

            # Add credentials if provided
            if self.settings.aws_access_key_id:
                client_kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
            if self.settings.aws_secret_access_key:
                client_kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key
            
            # Custom endpoint for MinIO/LocalStack
            if self.settings.s3_endpoint_url:
                client_kwargs["endpoint_url"] = self.settings.s3_endpoint_url

            self._client = boto3.client(**client_kwargs)
            logger.info(
                "S3 client initialized",
                bucket=self.settings.s3_bucket_name,
                region=self.settings.aws_region,
                custom_endpoint=bool(self.settings.s3_endpoint_url),
            )

        return self._client

    @property
    def bucket_name(self) -> str:
        """Get the configured bucket name."""
        return self.settings.s3_bucket_name

    def _generate_key(self, user_id: str, filename: str) -> str:
        """
        Generate a unique S3 key for a file.
        
        Format: uploads/{user_id}/{year}/{month}/{uuid}_{filename}
        """
        now = datetime.utcnow()
        unique_id = str(uuid4())[:8]
        safe_filename = self._sanitize_filename(filename)
        
        return f"uploads/{user_id}/{now.year}/{now.month:02d}/{unique_id}_{safe_filename}"

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for S3 key."""
        # Keep only alphanumeric, dots, dashes, underscores
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_")
        sanitized = "".join(c if c in safe_chars else "_" for c in filename)
        # Ensure it doesn't start with a dot
        if sanitized.startswith("."):
            sanitized = "_" + sanitized
        return sanitized[:255]  # Max filename length

    async def ensure_bucket(self) -> bool:
        """
        Ensure the S3 bucket exists.
        
        Returns:
            True if bucket exists or was created
        """
        if not self.settings.s3_enabled:
            logger.warning("S3 is not configured, skipping bucket check")
            return False

        try:
            client = self._get_client()
            
            # Check if bucket exists
            try:
                client.head_bucket(Bucket=self.bucket_name)
                logger.debug("S3 bucket exists", bucket=self.bucket_name)
                return True
            except client.exceptions.ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code == "404":
                    # Bucket doesn't exist, create it
                    logger.info("Creating S3 bucket", bucket=self.bucket_name)
                    
                    create_kwargs = {"Bucket": self.bucket_name}
                    
                    # LocationConstraint is required for non-us-east-1 regions
                    if self.settings.aws_region != "us-east-1":
                        create_kwargs["CreateBucketConfiguration"] = {
                            "LocationConstraint": self.settings.aws_region
                        }
                    
                    client.create_bucket(**create_kwargs)
                    logger.info("S3 bucket created", bucket=self.bucket_name)
                    return True
                else:
                    raise

        except Exception as e:
            logger.error("Failed to ensure S3 bucket", error=str(e))
            raise StorageError(
                message=f"Failed to ensure S3 bucket: {str(e)}",
                store_type="s3",
                operation="ensure_bucket",
                cause=e,
            )

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        user_id: str,
        content_type: Optional[str] = None,
    ) -> dict:
        """
        Upload a file to S3.
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            user_id: User ID for organizing uploads
            content_type: Optional MIME type
            
        Returns:
            Dict with s3_key, s3_bucket, and s3_url
        """
        if not self.settings.s3_enabled:
            raise StorageError(
                message="S3 is not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.",
                store_type="s3",
                operation="upload_file",
            )

        try:
            client = self._get_client()
            
            # Generate unique key
            s3_key = self._generate_key(user_id, filename)
            
            # Prepare upload parameters
            upload_kwargs = {
                "Bucket": self.bucket_name,
                "Key": s3_key,
                "Body": file_content,
            }
            
            # Add content type if provided
            if content_type:
                upload_kwargs["ContentType"] = content_type
            else:
                # Infer content type from extension
                ext = Path(filename).suffix.lower()
                content_types = {
                    ".pdf": "application/pdf",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".doc": "application/msword",
                    ".txt": "text/plain",
                    ".md": "text/markdown",
                }
                if ext in content_types:
                    upload_kwargs["ContentType"] = content_types[ext]

            # Upload
            client.put_object(**upload_kwargs)
            
            # Generate URL
            if self.settings.s3_endpoint_url:
                s3_url = f"{self.settings.s3_endpoint_url}/{self.bucket_name}/{s3_key}"
            else:
                s3_url = f"https://{self.bucket_name}.s3.{self.settings.aws_region}.amazonaws.com/{s3_key}"

            logger.info(
                "File uploaded to S3",
                bucket=self.bucket_name,
                key=s3_key,
                size=len(file_content),
                filename=filename,
            )

            return {
                "s3_key": s3_key,
                "s3_bucket": self.bucket_name,
                "s3_url": s3_url,
                "size_bytes": len(file_content),
                "original_filename": filename,
            }

        except Exception as e:
            logger.error("Failed to upload file to S3", filename=filename, error=str(e))
            raise StorageError(
                message=f"Failed to upload file to S3: {str(e)}",
                store_type="s3",
                operation="upload_file",
                cause=e,
            )

    async def download_file(self, s3_key: str) -> bytes:
        """
        Download a file from S3.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            File content as bytes
        """
        if not self.settings.s3_enabled:
            raise StorageError(
                message="S3 is not configured",
                store_type="s3",
                operation="download_file",
            )

        try:
            client = self._get_client()
            
            response = client.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response["Body"].read()
            
            logger.debug("File downloaded from S3", key=s3_key, size=len(content))
            return content

        except Exception as e:
            logger.error("Failed to download file from S3", key=s3_key, error=str(e))
            raise StorageError(
                message=f"Failed to download file from S3: {str(e)}",
                store_type="s3",
                operation="download_file",
                cause=e,
            )

    async def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if deleted successfully
        """
        if not self.settings.s3_enabled:
            return False

        try:
            client = self._get_client()
            client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info("File deleted from S3", key=s3_key)
            return True

        except Exception as e:
            logger.error("Failed to delete file from S3", key=s3_key, error=str(e))
            return False

    async def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
        for_download: bool = True,
    ) -> str:
        """
        Generate a presigned URL for file access.
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration in seconds (default: 1 hour)
            for_download: If True, generates download URL; if False, upload URL
            
        Returns:
            Presigned URL
        """
        if not self.settings.s3_enabled:
            raise StorageError(
                message="S3 is not configured",
                store_type="s3",
                operation="generate_presigned_url",
            )

        try:
            client = self._get_client()
            
            if for_download:
                url = client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": s3_key},
                    ExpiresIn=expiration,
                )
            else:
                url = client.generate_presigned_url(
                    "put_object",
                    Params={"Bucket": self.bucket_name, "Key": s3_key},
                    ExpiresIn=expiration,
                )

            return url

        except Exception as e:
            logger.error("Failed to generate presigned URL", key=s3_key, error=str(e))
            raise StorageError(
                message=f"Failed to generate presigned URL: {str(e)}",
                store_type="s3",
                operation="generate_presigned_url",
                cause=e,
            )

    async def list_user_files(
        self,
        user_id: str,
        prefix: Optional[str] = None,
        max_keys: int = 100,
    ) -> list[dict]:
        """
        List files uploaded by a user.
        
        Args:
            user_id: User ID
            prefix: Additional prefix filter within user's uploads
            max_keys: Maximum number of keys to return
            
        Returns:
            List of file info dicts
        """
        if not self.settings.s3_enabled:
            return []

        try:
            client = self._get_client()
            
            s3_prefix = f"uploads/{user_id}/"
            if prefix:
                s3_prefix += prefix

            response = client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=s3_prefix,
                MaxKeys=max_keys,
            )

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "filename": Path(obj["Key"]).name,
                })

            return files

        except Exception as e:
            logger.error("Failed to list user files", user_id=user_id, error=str(e))
            return []

    async def close(self):
        """Close the S3 client."""
        self._client = None

