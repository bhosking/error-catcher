#
# notifyOnError Lambda Function
#
data "aws_iam_policy_document" "lambda-notifyOnError" {

  statement {
    actions = [
      "cloudwatch:DescribeAlarms",
    ]
    resources = [
      aws_cloudwatch_metric_alarm.notifyOnError-alarm.arn,
    ]
  }

  statement {
    actions = [
      "events:describeRule",
      "events:enableRule",
      "events:disableRule",
    ]
    resources = [
      aws_cloudwatch_event_rule.notifyOnError-trigger.arn,
    ]
  }

  statement {
    actions = [
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.recent-errors.arn,
    ]
  }

  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [
      "${aws_s3_bucket.recent-errors.arn}/*",
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
      "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.this.account_id}:log-group:/aws/lambda/*",
    ]
  }

  statement {
    actions = [
      "ses:SendEmail"
    ]
    resources = [
      "arn:aws:ses:${data.aws_region.current.region}:${data.aws_caller_identity.this.account_id}:identity/*",
      "arn:aws:ses:${data.aws_region.current.region}:${data.aws_caller_identity.this.account_id}:configuration-set/*",
    ]
  }
}
