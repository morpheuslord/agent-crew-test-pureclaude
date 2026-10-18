output "ui_instance_profile_name" {
  description = "Instance profile of the UI instances."
  value       = aws_iam_instance_profile.this["ui"].name
}

output "api_instance_profile_name" {
  description = "Instance profile of the API instances."
  value       = aws_iam_instance_profile.this["api"].name
}

output "role_arns" {
  description = "ARNs of the instance roles, keyed by service."
  value       = { for service, role in aws_iam_role.this : service => role.arn }
}
