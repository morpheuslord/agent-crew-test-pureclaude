output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "IDs of the public subnets (load balancer and NAT gateways)."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets (instances, database, cache)."
  value       = aws_subnet.private[*].id
}

output "nat_public_ips" {
  description = "Public addresses of the NAT gateways; outbound webhooks come from these."
  value       = aws_eip.nat[*].public_ip
}
