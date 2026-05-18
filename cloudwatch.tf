resource "aws_cloudwatch_metric_alarm" "notifyOnError_alarm" {
  alarm_name          = "${var.prefix}-notifyOnError"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = local.recent_errors_minutes * 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Alarm if any Lambda function in the region has errors"
  alarm_actions       = [aws_sns_topic.notifyOnError.arn]
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_event_rule" "notifyOnError_trigger" {
  name                = "${var.prefix}-notifyOnError-trigger"
  description         = "A trigger that runs the notifyOnError lambda function while the alarm is in ALARM state."
  schedule_expression = "cron(*/20 * * * ? *)" # every 20 minutes
}

resource "aws_cloudwatch_event_target" "notifyOnError_trigger" {
  rule      = aws_cloudwatch_event_rule.notifyOnError_trigger.name
  target_id = "${var.prefix}-lambda-notifyOnError"
  arn       = module.lambda_notifyOnError.lambda_function_arn
}
