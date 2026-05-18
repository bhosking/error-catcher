#
# notifyOnError Lambda Function
#
data "aws_iam_policy_document" "lambda_notifyOnError" {

  statement {
    actions = [
      "cloudwatch:DescribeAlarms",
    ]
    resources = [
      aws_cloudwatch_metric_alarm.notifyOnError_alarm.arn,
    ]
  }

  statement {
    actions = [
      "events:describeRule",
      "events:enableRule",
      "events:disableRule",
    ]
    resources = [
      aws_cloudwatch_event_rule.notifyOnError_trigger.arn,
    ]
  }

  statement {
    actions = [
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.recent_errors.arn,
    ]
  }

  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [
      "${aws_s3_bucket.recent_errors.arn}/*",
    ]
  }

  statement {
    actions = [
      "cloudwatch:ListMetrics",
      "cloudwatch:GetMetricData",
    ]
    resources = [
      "*",
    ]
  }

  statement {
    actions = [
      "logs:FilterLogEvents",
    ]
    resources = [
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.this.account_id}:log-group:/aws/lambda/*",
    ]
  }

  statement {
    actions = [
      "sns:Publish",
    ]
    resources = [
      aws_sns_topic.error_notifications.arn,
    ]
  }
}
