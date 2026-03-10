resource "aws_sqs_queue" "job_dlq" {
  name                      = "code-quality-jobs-dlq"
  message_retention_seconds = 1209600
}

# 2. The Main Job Queue
resource "aws_sqs_queue" "job_queue" {
  name = "code-quality-jobs"


  visibility_timeout_seconds = 600 
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.job_dlq.arn
    maxReceiveCount     = 3
  })
}