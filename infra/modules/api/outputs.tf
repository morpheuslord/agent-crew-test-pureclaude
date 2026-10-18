output "security_group_id" {
  description = "Security group of the API instances."
  value       = aws_security_group.api.id
}

output "load_balancer_security_group_id" {
  description = "Security group of the internal API load balancer."
  value       = aws_security_group.lb.id
}

output "internal_url" {
  description = "Base URL of the internal API load balancer (reachable from the UI instances only)."
  value       = "http://${aws_lb.internal.dns_name}"
}

output "instance_ids" {
  description = "IDs of the API instances (connect with SSM Session Manager, e.g. to run create-admin)."
  value       = aws_instance.api[*].id
}

output "log_group_name" {
  description = "CloudWatch log group of the API containers."
  value       = aws_cloudwatch_log_group.api.name
}
