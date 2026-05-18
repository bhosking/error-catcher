resource "aws_cloudwatch_metric_alarm" "notifyOnError-alarm" {
  alarm_name          = "error-catcher-notifyOnError"
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

resource "aws_cloudwatch_event_rule" "notifyOnError-trigger" {
  name                = "error-catcher-notifyOnError-trigger"
  description         = "A trigger that runs the notifyOnError lambda function while the alarm is in ALARM state."
  schedule_expression = "cron(*/20 * * * ? *)" # every 20 minutes
}

resource "aws_cloudwatch_event_target" "notifyOnError-trigger" {
  rule      = aws_cloudwatch_event_rule.notifyOnError-trigger.name
  target_id = "error-catcher-lambda-notifyOnError"
  arn       = module.lambda-notifyOnError.lambda_function_arn
}
