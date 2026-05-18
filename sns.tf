resource "aws_sns_topic" "notifyOnError" {
  name = "error-catcher-notifyOnError"
}

resource "aws_sns_topic_subscription" "notifyOnError" {
  topic_arn = aws_sns_topic.notifyOnError.arn
  protocol  = "lambda"
  endpoint  = module.lambda-notifyOnError.lambda_function_arn
}
