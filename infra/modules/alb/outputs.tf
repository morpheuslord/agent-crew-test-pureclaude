output "dns_name" {
  description = "DNS name of the public load balancer; point the application's DNS record here."
  value       = aws_lb.this.dns_name
}

output "zone_id" {
  description = "Route 53 hosted zone ID of the load balancer, for an alias record."
  value       = aws_lb.this.zone_id
}

output "security_group_id" {
  description = "Security group of the load balancer."
  value       = aws_security_group.alb.id
}

output "target_group_arn" {
  description = "Target group the UI instances register with."
  value       = aws_lb_target_group.ui.arn
}

output "access_log_bucket" {
  description = "Bucket receiving load balancer access logs."
  value       = aws_s3_bucket.logs.id
}
