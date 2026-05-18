provider "aws" {
  region = var.region

  default_tags {
    tags = var.common_tags
  }
}
