#
# notifyOnError Lambda Function
#
resource "aws_lambda_permission" "SNS_notifyOnError" {
  statement_id  = "${var.prefix}-AllowSNSnotifyOnErrorInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_notifyOnError.lambda_function_arn
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.notifyOnError.arn
}

resource "aws_lambda_permission" "cloudwatch_notifyOnError" {
  statement_id  = "${var.prefix}-AllowCloudwatchNotifyOnErrorInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_notifyOnError.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.notifyOnError_trigger.arn
}
