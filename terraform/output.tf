output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer."
  value       = aws_lb.api_lb.dns_name
}

output "nat_gateway_public_ips" {
  description = "Public IPs of the managed NAT Gateway(s)."
  value       = module.vpc.nat_public_ips
}

output "db_endpoint" {
  description = "PostgreSQL endpoint for psql connections from inside the VPC."
  value       = aws_db_instance.metadata_db.address
}

output "debug_instance_public_ip" {
  description = "Public IP of the optional debug EC2 instance."
  value       = var.enable_debug_instance ? aws_instance.db_debug[0].public_ip : null
}

output "debug_instance_ssh_hint" {
  description = "SSH command template for the optional debug EC2 instance."
  value       = var.enable_debug_instance ? "ssh -i <path-to-private-key> ec2-user@${aws_instance.db_debug[0].public_ip}" : null
}
