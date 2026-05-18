# SES variables
variable "ses-source-email" {
  type        = string
  description = "Address from which to send emails"
}

variable "ses-target-emails" {
  type        = list(string)
  description = "Email addresses to notify when errors occur."
}
