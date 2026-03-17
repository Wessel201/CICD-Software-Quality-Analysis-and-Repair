# 1. The Firewall: Workers only need to speak OUT, never IN.
resource "aws_security_group" "worker_sg" {
  name        = "worker-ecs-sg"
  description = "Security group for background workers"
  vpc_id      = module.vpc.vpc_id

  # Notice: NO INGRESS RULES! Nothing on the internet can reach inside this container.

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"] # Allowed to reach the internet (via your EC2 NAT)
  }
}

# 2. The Worker Task Definition (The Hardware & Docker Config)
resource "aws_ecs_task_definition" "worker_task" {
  family                   = "worker-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  
  # We give the worker slightly more power than the API because 
  # running static analysis (AST parsing) on large Python/C++ repos uses RAM.
  cpu                      = "512"  # 0.5 vCPU
  memory                   = "1024" # 1 GB RAM
  
  # IAM Roles (Assuming you define these in an iam.tf file later)
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.worker_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "worker-container"
      image     = "python:3.11-slim" # PLACEHOLDER: CI/CD will update this to your ECR image
      essential = true
      
      # NO portMappings here. The worker doesn't listen on ports.

      # Injecting the environment variables the Python code needs to function
      environment = [
        { name = "SQS_QUEUE_URL", value = aws_sqs_queue.job_queue.url },
        { name = "S3_BUCKET_NAME", value = aws_s3_bucket.artifact_storage.bucket },
        { name = "DB_HOST", value = aws_db_instance.metadata_db.address },
        { name = "DB_PASSWORD", value = var.db_password }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/worker"
          "awslogs-region"        = "eu-central-1"
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# 3. The ECS Service (Keeps the Worker Alive)
resource "aws_ecs_service" "worker_service" {
  name            = "worker-service"
  cluster         = aws_ecs_cluster.main_cluster.id # Reusing the cluster from api.tf
  task_definition = aws_ecs_task_definition.worker_task.arn
  desired_count   = 0
  launch_type     = "FARGATE"

  network_configuration {
    # Place containers strictly in PRIVATE subnets.
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.worker_sg.id]
    assign_public_ip = false
  }
  lifecycle {
    ignore_changes = [desired_count] # Let the Auto-Scaler control this!
  }
}