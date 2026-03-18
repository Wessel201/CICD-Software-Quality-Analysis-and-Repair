output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer."
  value       = aws_lb.api_lb.dns_name
}

output "nat_gateway_public_ips" {
  description = "Public IPs of the managed NAT Gateway(s)."
  value       = module.vpc.nat_public_ips
}
