output "host" {
  description = "Primary endpoint of the cache (TLS)."
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "port" {
  description = "Port of the cache."
  value       = aws_elasticache_replication_group.this.port
}

output "auth_token_secret_arn" {
  description = "Secrets Manager secret holding the cache AUTH token."
  value       = aws_secretsmanager_secret.auth_token.arn
}

output "security_group_id" {
  description = "Security group of the cache."
  value       = aws_security_group.cache.id
}
