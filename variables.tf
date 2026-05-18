variable "common_tags" {
  type        = map(string)
  description = "A set of tags to attach to every created resource."
}

variable "region" {
  type        = string
  description = "AWS region"
}

variable "sns_target_emails" {
  type        = list(string)
  description = "Email addresses to notify when errors occur."
}

variable "prefix" {
  type        = string
  description = "A unique and meaningful prefix added to the name of every created resource and as the Prefix tag. For sorting, identification and to avoid name collisions."
}
