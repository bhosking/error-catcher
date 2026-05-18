resource "aws_s3_bucket" "recent-errors" {
  bucket_prefix = "error-catcher-recent-errors-"
  force_destroy = true
}

resource "aws_s3_bucket_lifecycle_configuration" "recent-errors-lifecycle" {
  bucket = aws_s3_bucket.recent-errors.id

  rule {
    id     = "remove-old-files"
    status = "Enabled"

    filter {}

    expiration {
      days = 1
    }
  }
}
