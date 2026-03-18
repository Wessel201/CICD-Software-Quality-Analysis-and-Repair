import os
import json
import uuid
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Any, Tuple

from fastapi import HTTPException

class CloudQualityManager:
    def __init__(self):
        region = os.getenv("AWS_REGION", "eu-central-1")
        self.s3_client = boto3.client("s3", region_name=region)
        self.sqs_client = boto3.client("sqs", region_name=region)

        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.queue_url = os.getenv("SQS_QUEUE_URL")
        self.logger = logging.getLogger(__name__)

    def generate_upload_url(self, user_id: int, filename: str) -> Tuple[str, str]:
        """
        Generates a secure, temporary S3 URL so the user's browser can upload 
        the ZIP file directly to AWS, bypassing your API's memory.
        """
        # Create a unique path: uploads/user_123/job_abc123.zip
        job_id = str(uuid.uuid4())
        if not self.bucket_name:
            raise HTTPException(status_code=500, detail="S3_BUCKET_NAME is not configured.")

        safe_name = filename.replace("/", "_").replace("..", "_")
        s3_key = f"uploads/user_{user_id}/job_{job_id}_{safe_name}"
        self.logger.info("Generating upload URL", extra={"event": "s3_upload_url_start"})
        
        try:
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key,
                },
                ExpiresIn=300 # URL expires in 5 minutes for security
            )
            self.logger.info("Generated upload URL", extra={"event": "s3_upload_url_success"})
            return presigned_url, s3_key
        except ClientError as e:
            self.logger.exception("Error generating presigned URL", extra={"event": "s3_upload_url_failed"})
            raise HTTPException(status_code=500, detail="Failed to generate upload URL.") from e

    def generate_download_url(self, storage_key: str, expires_in_seconds: int = 300) -> str:
        if not self.bucket_name:
            raise HTTPException(status_code=500, detail="S3_BUCKET_NAME is not configured.")

        try:
            self.logger.info("Generating download URL", extra={"event": "s3_download_url_start"})
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": storage_key},
                ExpiresIn=expires_in_seconds,
            )
        except ClientError as e:
            self.logger.exception("Failed to generate download URL", extra={"event": "s3_download_url_failed"})
            raise HTTPException(status_code=500, detail="Failed to generate artifact download URL.") from e

    def submit_job(self, payload: dict[str, Any]) -> None:
        """Pushes a job payload to the SQS queue to wake worker containers."""
        if not self.queue_url:
            raise HTTPException(status_code=500, detail="SQS_QUEUE_URL is not configured.")

        try:
            self.logger.info("Submitting job to SQS", extra={"event": "sqs_submit_start", "job_id": payload.get("job_id")})
            self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(payload),
            )
            self.logger.info("Submitted job to SQS", extra={"event": "sqs_submit_success", "job_id": payload.get("job_id")})
        except ClientError as e:
            self.logger.exception("Failed to submit job to SQS", extra={"event": "sqs_submit_failed", "job_id": payload.get("job_id")})
            raise HTTPException(status_code=500, detail="Failed to submit job to SQS.") from e