locals {
  # Define the time period for which to track recent errors
  # This should be at least 15 minutes (lambda timeout) plus 20 minutes (trigger interval)
  recent_errors_minutes = 40
}

data "aws_caller_identity" "this" {}
data "aws_default_tags" "this" {}
data "aws_region" "current" {}

#
# notifyOnError Lambda Function
#
module "lambda-notifyOnError" {
  source = "terraform-aws-modules/lambda/aws"

  function_name                  = "error-catcher-notifyOnError"
  description                    = "Notifies admin when lambda functions encounter an error."
  handler                        = "lambda_function.lambda_handler"
  runtime                        = "python3.13"
  memory_size                    = 512
  timeout                        = 300
  reserved_concurrent_executions = 1 # To avoid duplicated emails
  attach_policy_json             = true
  policy_json                    = data.aws_iam_policy_document.lambda-notifyOnError.json
  source_path                    = "${path.module}/lambda/notifyOnError"
  tags                           = data.aws_default_tags.this.tags

  environment_variables = {
    ACCOUNT_ID            = data.aws_caller_identity.this.account_id
    ALARM_NAME            = aws_cloudwatch_metric_alarm.notifyOnError-alarm.alarm_name
    RECENT_ERRORS_BUCKET  = aws_s3_bucket.recent-errors.bucket
    RECENT_ERRORS_MINUTES = local.recent_errors_minutes
    SES_SOURCE_EMAIL      = var.ses-source-email
    SES_TARGET_EMAIL      = var.ses-target-email
    TRIGGER_NAME          = aws_cloudwatch_event_rule.notifyOnError-trigger.name
  }
}
