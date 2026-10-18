output "bucket_name" {
  description = "Name of the attachments bucket."
  value       = aws_s3_bucket.attachments.id
}

output "bucket_arn" {
  description = "ARN of the attachments bucket."
  value       = aws_s3_bucket.attachments.arn
}

output "access_log_bucket_name" {
  description = "Bucket receiving S3 server access logs for the attachments bucket."
  value       = aws_s3_bucket.access_logs.id
}
