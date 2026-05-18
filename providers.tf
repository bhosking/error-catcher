provider "aws" {
  region = var.region

  default_tags {
    tags = merge(var.common_tags, { Prefix = var.prefix })
  }
}
