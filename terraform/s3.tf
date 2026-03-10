resource "aws_s3_bucket" "artifact_storage" {
  bucket = "code-quality-artifacts-bucket-prod"
}

resource "aws_s3_bucket_public_access_block" "artifact_storage_block" {
  bucket                  = aws_s3_bucket.artifact_storage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifact_storage_sse" {
  bucket = aws_s3_bucket.artifact_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# The automated cost-saver: Delete raw uploads after 7 days
resource "aws_s3_bucket_lifecycle_configuration" "artifact_lifecycle" {
  bucket = aws_s3_bucket.artifact_storage.id

  rule {
    id     = "auto-delete-old-uploads"
    status = "Enabled"

    filter {
      prefix = "uploads/"
    }

    expiration {
      days = 7
    }
  }
}