variable "common_tags" {
  type        = map(string)
  description = "A set of tags to attach to every created resource."
}

variable "region" {
  type        = string
  description = "AWS region"
}

variable "ses_source_email" {
  type        = string
  description = "Address from which to send emails"
}

variable "ses_target_emails" {
  type        = list(string)
  description = "Email addresses to notify when errors occur."
}
