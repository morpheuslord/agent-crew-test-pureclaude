output "host" {
  description = "Hostname of the PostgreSQL endpoint."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "Port of the PostgreSQL endpoint."
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "Name of the application database."
  value       = aws_db_instance.this.db_name
}

output "master_user_secret_arn" {
  description = "Secrets Manager secret (managed by RDS) with the master user name and password."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "security_group_id" {
  description = "Security group of the database."
  value       = aws_security_group.db.id
}
