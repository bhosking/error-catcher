data "aws_caller_identity" "this" {}

#
# notifyOnError Lambda Function
#
module "lambda_notifyOnError" {
  source = "terraform-aws-modules/lambda/aws"
  version = "= 8.1.1"

  function_name                  = "${var.prefix}-notifyOnError"
  description                    = "Notifies admin when lambda functions encounter an error."
  handler                        = "lambda_function.lambda_handler"
  runtime                        = "python3.14"
  architectures                  = ["arm64"]
  memory_size                    = 512
  timeout                        = 300
  reserved_concurrent_executions = 1 # To avoid duplicated emails
  attach_policy_json             = true
  policy_json                    = data.aws_iam_policy_document.lambda_notifyOnError.json
  source_path                    = "${path.module}/lambda/notifyOnError"

  environment_variables = {
    ACCOUNT_ID            = data.aws_caller_identity.this.account_id
    ALARM_NAME            = aws_cloudwatch_metric_alarm.notifyOnError_alarm.alarm_name
    RECENT_ERRORS_BUCKET  = aws_s3_bucket.recent_errors.bucket
    RECENT_ERRORS_MINUTES = local.recent_errors_minutes
    ERROR_NOTIFICATIONS_SNS_TOPIC_ARN = aws_sns_topic.error_notifications.arn
    TRIGGER_NAME          = aws_cloudwatch_event_rule.notifyOnError_trigger.name
  }
}
