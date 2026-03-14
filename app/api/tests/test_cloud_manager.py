import json

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.cloud import CloudQualityManager


class FakeS3:
    def __init__(self):
        self.calls = []
        self.fail = False

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        self.calls.append((operation, Params, ExpiresIn))
        if self.fail:
            raise ClientError({"Error": {"Code": "Boom", "Message": "x"}}, operation)
        return "https://example.com/presigned"


class FakeSqs:
    def __init__(self):
        self.calls = []
        self.fail = False

    def send_message(self, QueueUrl, MessageBody):
        self.calls.append((QueueUrl, MessageBody))
        if self.fail:
            raise ClientError({"Error": {"Code": "Boom", "Message": "x"}}, "SendMessage")


@pytest.fixture
def cloud_clients(monkeypatch):
    s3 = FakeS3()
    sqs = FakeSqs()

    def fake_client(name, region_name=None):
        if name == "s3":
            return s3
        if name == "sqs":
            return sqs
        raise AssertionError(name)

    monkeypatch.setattr("app.cloud.boto3.client", fake_client)
    return s3, sqs


def test_generate_upload_url_success(monkeypatch, cloud_clients):
    s3, _ = cloud_clients
    monkeypatch.setenv("AWS_REGION", "eu-central-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")
    monkeypatch.setenv("SQS_QUEUE_URL", "https://queue")

    manager = CloudQualityManager()
    url, key = manager.generate_upload_url(user_id=42, filename="../repo.zip")

    assert url == "https://example.com/presigned"
    assert key.startswith("uploads/user_42/job_")
    assert ".." not in key
    assert "/../" not in key
    assert s3.calls[0][0] == "put_object"


def test_generate_upload_url_requires_bucket(monkeypatch, cloud_clients):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.setenv("SQS_QUEUE_URL", "https://queue")
    manager = CloudQualityManager()

    with pytest.raises(HTTPException) as exc_info:
        manager.generate_upload_url(user_id=1, filename="repo.zip")
    assert exc_info.value.status_code == 500


def test_generate_upload_url_client_error(monkeypatch, cloud_clients):
    s3, _ = cloud_clients
    s3.fail = True
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")
    monkeypatch.setenv("SQS_QUEUE_URL", "https://queue")
    manager = CloudQualityManager()

    with pytest.raises(HTTPException, match="Failed to generate upload URL"):
        manager.generate_upload_url(user_id=1, filename="repo.zip")


def test_generate_download_url_success(monkeypatch, cloud_clients):
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")
    monkeypatch.setenv("SQS_QUEUE_URL", "https://queue")
    manager = CloudQualityManager()

    url = manager.generate_download_url("uploads/a.zip", expires_in_seconds=60)
    assert url == "https://example.com/presigned"


def test_generate_download_url_requires_bucket(monkeypatch, cloud_clients):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.setenv("SQS_QUEUE_URL", "https://queue")
    manager = CloudQualityManager()

    with pytest.raises(HTTPException, match="S3_BUCKET_NAME"):
        manager.generate_download_url("uploads/a.zip")


def test_generate_download_url_client_error(monkeypatch, cloud_clients):
    s3, _ = cloud_clients
    s3.fail = True
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")
    monkeypatch.setenv("SQS_QUEUE_URL", "https://queue")
    manager = CloudQualityManager()

    with pytest.raises(HTTPException, match="Failed to generate artifact download URL"):
        manager.generate_download_url("uploads/a.zip")


def test_submit_job_success(monkeypatch, cloud_clients):
    _, sqs = cloud_clients
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")
    monkeypatch.setenv("SQS_QUEUE_URL", "https://queue")
    manager = CloudQualityManager()

    manager.submit_job({"job_id": "job_1", "action": "analyze"})
    assert len(sqs.calls) == 1
    queue_url, body = sqs.calls[0]
    assert queue_url == "https://queue"
    assert json.loads(body)["job_id"] == "job_1"


def test_submit_job_requires_queue(monkeypatch, cloud_clients):
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")
    monkeypatch.delenv("SQS_QUEUE_URL", raising=False)
    manager = CloudQualityManager()

    with pytest.raises(HTTPException, match="SQS_QUEUE_URL"):
        manager.submit_job({"job_id": "job_1"})


def test_submit_job_client_error(monkeypatch, cloud_clients):
    _, sqs = cloud_clients
    sqs.fail = True
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket")
    monkeypatch.setenv("SQS_QUEUE_URL", "https://queue")
    manager = CloudQualityManager()

    with pytest.raises(HTTPException, match="Failed to submit job to SQS"):
        manager.submit_job({"job_id": "job_1"})
