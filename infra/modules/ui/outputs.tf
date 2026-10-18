output "security_group_id" {
  description = "Security group of the UI instances."
  value       = aws_security_group.ui.id
}

output "instance_ids" {
  description = "IDs of the UI instances (connect with SSM Session Manager)."
  value       = aws_instance.ui[*].id
}

output "log_group_name" {
  description = "CloudWatch log group of the UI containers."
  value       = aws_cloudwatch_log_group.ui.name
}
