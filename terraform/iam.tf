data "aws_iam_policy_document" "ecs_trust_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution_role" {
  name               = "code-quality-ecs-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust_policy.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}


resource "aws_iam_role" "api_task_role" {
  name               = "code-quality-api-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust_policy.json
}

resource "aws_iam_role_policy" "api_permissions" {
  name = "api-permissions-policy"
  role = aws_iam_role.api_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueUrl"
        ]
        Resource = aws_sqs_queue.job_queue.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = [
          "${aws_s3_bucket.artifact_storage.arn}/uploads/*",
          "${aws_s3_bucket.artifact_storage.arn}/reports/*"
        ]
      }
    ]
  })
}


resource "aws_iam_role" "worker_task_role" {
  name               = "code-quality-worker-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust_policy.json
}


resource "aws_iam_role_policy" "worker_permissions" {
  name = "worker-permissions-policy"
  role = aws_iam_role.worker_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.job_queue.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "${aws_s3_bucket.artifact_storage.arn}/uploads/*",
          "${aws_s3_bucket.artifact_storage.arn}/reports/*"
        ]
      }
    ]
  })
}