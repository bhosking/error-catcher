#
# notifyOnError Lambda Function
#
resource "aws_lambda_permission" "SNS-notifyOnError" {
  statement_id  = "ErrorCatcherAllowSNSnotifyOnErrorInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda-notifyOnError.lambda_function_arn
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.notifyOnError.arn
}

resource "aws_lambda_permission" "cloudwatch-notifyOnError" {
  statement_id  = "ErrorCatcherCloudwatchNotifyOnErrorInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda-notifyOnError.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.notifyOnError-trigger.arn
}
