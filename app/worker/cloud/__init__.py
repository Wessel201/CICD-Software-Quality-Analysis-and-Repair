import os
import json
import boto3
import zipfile
import psycopg2
import subprocess
from openai import OpenAI
from botocore.exceptions import ClientError

class CloudWorkerManager:
    def __init__(self):
        # 1. Initialize AWS & External Clients
        self.s3_client = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'eu-central-1'))
        self.sqs_client = boto3.client('sqs', region_name=os.getenv('AWS_REGION', 'eu-central-1'))
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # 2. Environment Variables
        self.queue_url = os.getenv('SQS_QUEUE_URL')
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        self.db_host = os.getenv('DB_HOST')
        self.db_name = os.getenv('DB_NAME', 'codequality')
        self.db_user = os.getenv('DB_USER', 'postgres_admin')
        self.db_password = os.getenv('DB_PASSWORD')
        
        # 3. Safeguards (Advanced Deliverable Requirements)
        self.max_repair_cycles = 3

    def _get_db_connection(self):
        return psycopg2.connect(
            host=self.db_host, database=self.db_name,
            user=self.db_user, password=self.db_password
        )

    def fetch_job(self):
        """Long-polls SQS for up to 20 seconds waiting for a new job."""
        response = self.sqs_client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20 # Keeps AWS API costs to an absolute minimum
        )
        messages = response.get('Messages', [])
        return messages[0] if messages else None

    def delete_job(self, receipt_handle: str):
        """Tells SQS we finished the job so it doesn't send it to another worker."""
        self.sqs_client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=receipt_handle
        )

    def download_and_extract(self, s3_key: str, download_path: str, extract_path: str):
        """Pulls the ZIP from S3 and unpacks it for analysis."""
        self.s3_client.download_file(self.bucket_name, s3_key, download_path)
        with zipfile.ZipFile(download_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

    def run_analysis(self, source_dir: str) -> dict:
        """Runs Bandit to find security flaws. (You can add Pylint/Radon here too)."""
        # We use subprocess to run the CLI tool and capture the JSON output
        result = subprocess.run(
            ['bandit', '-r', source_dir, '-f', 'json'],
            capture_output=True, text=True
        )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"results": [], "errors": "Failed to parse Bandit output"}