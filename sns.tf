resource "aws_sns_topic" "notifyOnError" {
  name = "${var.prefix}-notifyOnError"
}

resource "aws_sns_topic_subscription" "notifyOnError" {
  topic_arn = aws_sns_topic.notifyOnError.arn
  protocol  = "lambda"
  endpoint  = module.lambda_notifyOnError.lambda_function_arn
}

resource "aws_sns_topic" "error_notifications" {
  name = "${var.prefix}-error-notifications"
}

resource "aws_sns_topic_subscription" "error_notifications" {
  for_each  = toset(var.sns_target_emails)
  topic_arn = aws_sns_topic.error_notifications.arn
  protocol  = "email"
  endpoint  = each.value
}
