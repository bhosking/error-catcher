# error-catcher

A Terraform module that monitors all AWS Lambda functions in a region for errors and sends email notifications via SES.

## How it works

A CloudWatch alarm triggers when any Lambda function reports errors. This invokes a `notifyOnError` Lambda function that:

1. Queries CloudWatch metrics to find which functions had errors
2. Searches CloudWatch Logs around the error timestamps to find matching log events
3. Groups errors by message (with fuzzy matching to deduplicate similar errors)
4. Sends an HTML email via SES listing each new error, its count, and a direct link to the log event in CloudWatch

To handle the case where the alarm only fires on state changes (not continuously), the function also enables a recurring EventBridge schedule (every 20 minutes) while the alarm is active, and disables it once the alarm clears.

Recent errors are tracked in S3 so that the same error is not reported more than once across invocations.

If an error metric has no matching log event (e.g. an unrecognised error format), the email includes a fallback link to the log group with a note that manual inspection is required.

## Architecture

- **CloudWatch alarm** — triggers when the sum of `AWS/Lambda Errors` across all functions exceeds 0 over the monitoring window
- **SNS topic** — receives alarm state changes and invokes the Lambda
- **EventBridge rule** — runs every 20 minutes; enabled/disabled dynamically by the Lambda based on alarm state
- **`notifyOnError` Lambda**  — core notification logic
- **S3 bucket** — stores recent error state to prevent duplicate notifications

## Usage

Recommended to create a `backend.tf` file to store the state remotely, here shown referencing an (existing) S3 bucket:

```hcl
terraform {
  backend "s3" {
    bucket       = "terraform-states"
    key          = "error-catcher-apse2.tfstate"
    region       = "ap-southeast-2"
    use_lockfile = true
  }
}
```

Create a `terraform.tfvars` file:

```hcl
region            = "ap-southeast-2"
prefix            = "error-catcher-apse2"
common_tags       = { Project = "myproject", Environment = "prod" }
ses_source_email  = "alerts@example.com"
ses_target_emails = ["admin@example.com", "oncall@example.com"]
```

Then deploy:

```shell
terraform init
terraform apply
```

All email addresses must be verified in SES. The source email address can be one of the target email addresses.

## Requirements

| Name | Version |
|------|---------|
| Terraform | >= 1.5.7 |
| AWS provider | >= 5.0 |

## Inputs

| Name | Description |
|------|-------------|
| `region` | AWS region to deploy into |
| `prefix` | Prefix added to all resource names and as a tag, for identification and to avoid collisions |
| `common_tags` | Map of tags applied to all resources |
| `ses_source_email` | Address from which alert emails are sent (must be verified in SES) |
| `ses_target_emails` | List of email addresses to notify when errors occur (each must be verified in SES) |

## Manual invocation

The Lambda can be invoked directly with a custom time window (useful for testing or backfilling):

```json
{
  "start_ms": 1700000000000,
  "end_ms":   1700003600000
}
```

When invoked this way, duplicate-suppression is skipped and error checking occurs regardless of alarm state.
