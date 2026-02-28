"""
Cloudflare R2 Storage Service
"""
import os
import logging
from datetime import datetime
from typing import Optional, BinaryIO
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from app.core.config import settings

logger = logging.getLogger(__name__)

class R2StorageService:
    """Cloudflare R2 storage service using boto3"""
    
    def __init__(self):
        self._client = None
        self._endpoint_url = settings.R2_ENDPOINT
        self._aws_access_key_id = settings.R2_ACCESS_KEY_ID
        self._aws_secret_access_key = settings.R2_SECRET_ACCESS_KEY
        self._bucket_name = settings.R2_BUCKET or "acs-hrms-storage"

        logger.info(
            f"R2 Config: "
            f"ENDPOINT_PRESENT={bool(self._endpoint_url)}, "
            f"ACCESS_KEY_PRESENT={bool(self._aws_access_key_id)}, "
            f"SECRET_KEY_PRESENT={bool(self._aws_secret_access_key)}, "
            f"BUCKET_PRESENT={bool(self._bucket_name)}"
        )
    
    def _ensure_client(self):
        """Lazy initialization of R2 client"""
        if self._client is not None:
            return
        
        if not all([self._endpoint_url, self._aws_access_key_id, self._aws_secret_access_key]):
            logger.error("Missing required R2 environment variables")
            raise ValueError("R2 configuration incomplete. Please set R2_ENDPOINT, R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY")
        
        try:
            self._client = boto3.client(
                's3',
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._aws_access_key_id,
                aws_secret_access_key=self._aws_secret_access_key,
                region_name="auto",
                config=boto3.session.Config(signature_version='s3v4')
            )
            logger.info(f"R2 client initialized for bucket: {self._bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {e}")
            raise
    
    def upload_file(self, file_data: BinaryIO, object_key: str, content_type: str) -> bool:
        """Upload file to R2 bucket"""
        try:
            self._ensure_client()
            logger.info(f"Uploading to R2: bucket={self._bucket_name}, key={object_key}, type={content_type}")
            
            self._client.put_object(
                Bucket=self._bucket_name,
                Key=object_key,
                Body=file_data,
                ContentType=content_type
            )
            
            logger.info(f"Successfully uploaded: {object_key}")
            return True
            
        except ClientError as e:
            logger.error(f"R2 upload error: {e}")
            return False
        except NoCredentialsError:
            logger.error("R2 credentials not configured properly")
            return False
        except Exception as e:
            logger.error(f"Unexpected upload error: {e}")
            return False
    
    def get_file(self, object_key: str) -> Optional[bytes]:
        """Get file from R2 bucket"""
        try:
            self._ensure_client()
            logger.debug(f"Fetching from R2: {object_key}")
            
            response = self._client.get_object(
                Bucket=self._bucket_name,
                Key=object_key
            )
            
            return response['Body'].read()
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"File not found: {object_key}")
                return None
            logger.error(f"R2 fetch error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected fetch error: {e}")
            return None
    
    def delete_file(self, object_key: str) -> bool:
        """Delete file from R2 bucket"""
        try:
            self._ensure_client()
            self._client.delete_object(
                Bucket=self._bucket_name,
                Key=object_key
            )
            logger.info(f"Deleted from R2: {object_key}")
            return True
        except Exception as e:
            logger.error(f"R2 delete error: {e}")
            return False

    def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a pre-signed URL for an object"""
        try:
            self._ensure_client()
            url = self._client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self._bucket_name,
                    'Key': object_key
                },
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate pre-signed URL for {object_key}: {e}")
            return None

# Global instance
r2_storage = R2StorageService()

def get_r2_storage_service() -> R2StorageService:
    """Returns the global R2StorageService instance."""
    return r2_storage
