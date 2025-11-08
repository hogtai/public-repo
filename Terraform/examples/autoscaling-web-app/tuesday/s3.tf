resource "aws_s3_bucket" "project21_s3_bucket_84135" {
  bucket = "project21-s3-bucket-84135"
}

resource "aws_s3_bucket_versioning" "project21_s3_bucket_84135" {
  bucket = aws_s3_bucket.project21_s3_bucket_84135.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "project21_s3_bucket_84135_access_block" {
  bucket = aws_s3_bucket.project21_s3_bucket_84135.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_kms_key" "s3_bucket_key" {
  description             = "S3 bucket key for project21_s3_bucket_84135"
  deletion_window_in_days = 7
  key_usage               = "ENCRYPT_DECRYPT"
}

