resource "aws_s3_bucket" "project21_s3_bucket_84135" {
  bucket = "project21-s3-bucket-84135" // Create an S3 bucket named "project21-s3-bucket-84135"
}

resource "aws_s3_bucket_versioning" "project21_s3_bucket_84135" {
  bucket = aws_s3_bucket.project21_s3_bucket_84135.id // Enable versioning on the S3 bucket created above

  versioning_configuration {
    status = "Enabled" // Set versioning status to "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "project21_s3_bucket_84135_access_block" {
  bucket = aws_s3_bucket.project21_s3_bucket_84135.id // Block public access to the S3 bucket created above

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_kms_key" "s3_bucket_key" {
  description             = "S3 bucket key for project21_s3_bucket_84135" // Create an AWS KMS key for the S3 bucket created above
  deletion_window_in_days = 7
  key_usage               = "ENCRYPT_DECRYPT"
}
