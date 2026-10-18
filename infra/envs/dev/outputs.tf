output "alb_dns_name" {
  description = "DNS name of the public load balancer; create a CNAME or alias for public_url here."
  value       = module.alb.dns_name
}

output "alb_zone_id" {
  description = "Hosted zone ID of the load balancer, for a Route 53 alias record."
  value       = module.alb.zone_id
}

output "ecr_repository_urls" {
  description = "Where CI pushes the api and ui images."
  value       = module.registry.repository_urls
}

output "attachments_bucket" {
  description = "S3 bucket holding attachments."
  value       = module.storage.bucket_name
}

output "database_endpoint" {
  description = "PostgreSQL host (private)."
  value       = module.database.host
}

output "database_secret_arn" {
  description = "Secrets Manager secret with the database credentials (managed by RDS)."
  value       = module.database.master_user_secret_arn
}

output "cache_endpoint" {
  description = "Cache primary endpoint (private, TLS)."
  value       = module.cache.host
}

output "api_internal_url" {
  description = "Internal API base URL (reachable from the UI instances only)."
  value       = module.api.internal_url
}

output "ui_instance_ids" {
  description = "UI instance IDs, for SSM Session Manager."
  value       = module.ui.instance_ids
}

output "api_instance_ids" {
  description = "API instance IDs, for SSM Session Manager (e.g. to run create-admin)."
  value       = module.api.instance_ids
}

output "log_groups" {
  description = "CloudWatch log groups of the containers."
  value = {
    ui  = module.ui.log_group_name
    api = module.api.log_group_name
  }
}

output "ssm_parameter_names" {
  description = "SSM parameters holding generated application secrets."
  value = {
    service_token = aws_ssm_parameter.service_token.name
    ui_secret     = aws_ssm_parameter.ui_secret.name
  }
}

output "kms_key_arn" {
  description = "KMS key protecting this environment's data."
  value       = aws_kms_key.main.arn
}

output "nat_public_ips" {
  description = "Source addresses of outbound traffic, including webhooks (for receivers' allow-lists)."
  value       = module.network.nat_public_ips
}
