resource "aws_appautoscaling_target" "worker_target" {
  max_capacity       = 5
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.main_cluster.name}/${aws_ecs_service.worker_service.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}


resource "aws_appautoscaling_policy" "worker_scale_up" {
  name               = "worker-scale-up-policy"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker_target.resource_id
  scalable_dimension = aws_appautoscaling_target.worker_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker_target.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ExactCapacity"
    cooldown                = 0
    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_lower_bound = 0
      metric_interval_upper_bound = 3
      scaling_adjustment          = 1
    }

    step_adjustment {
      metric_interval_lower_bound = 3
      metric_interval_upper_bound = 6
      scaling_adjustment          = 2
    }

    step_adjustment {
      metric_interval_lower_bound = 6
      metric_interval_upper_bound = 9
      scaling_adjustment          = 3
    }

    step_adjustment {
      metric_interval_lower_bound = 9
      metric_interval_upper_bound = 12
      scaling_adjustment          = 4
    }

    step_adjustment {
      metric_interval_lower_bound = 12
      scaling_adjustment          = 5
    }
  }
}

resource "aws_appautoscaling_policy" "worker_scale_down" {
  name               = "worker-scale-down-policy"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker_target.resource_id
  scalable_dimension = aws_appautoscaling_target.worker_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker_target.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ExactCapacity" 
    cooldown                = 300 
    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = 0
    }
  }
}

# Trigger: If there is 1 or more jobs in the queue, WAKE UP!
resource "aws_cloudwatch_metric_alarm" "queue_not_empty" {
  alarm_name          = "code-quality-queue-not-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 30
  statistic           = "Maximum"
  threshold           = 0

  dimensions = {
    QueueName = aws_sqs_queue.job_queue.name
  }

  alarm_actions = [aws_appautoscaling_policy.worker_scale_up.arn]
}

resource "aws_cloudwatch_metric_alarm" "queue_empty" {
  alarm_name          = "code-quality-queue-empty"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 5
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  dimensions = {
    QueueName = aws_sqs_queue.job_queue.name
  }

  alarm_actions = [aws_appautoscaling_policy.worker_scale_down.arn]
}