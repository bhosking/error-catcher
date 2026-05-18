resource "aws_s3_bucket" "recent_errors" {
  bucket_prefix = "error-catcher-recent_errors-"
  force_destroy = true
}

resource "aws_s3_bucket_lifecycle_configuration" "recent_errors_lifecycle" {
  bucket = aws_s3_bucket.recent_errors.id

  rule {
    id     = "remove-old-files"
    status = "Enabled"

    filter {}

    expiration {
      days = 1
    }
  }
}
