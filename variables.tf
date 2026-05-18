# SES variables
variable "ses-source-email" {
  type        = string
  description = "Address from which to send emails"
}

variable "ses-target-email" {
  type        = string
  description = "Email address of the administrator to notify when errors occur."
}
