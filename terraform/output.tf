output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer."
  value       = aws_lb.api_lb.dns_name
}

output "nat_instance_public_ip" {
  description = "Public IP of the NAT instance."
  value       = aws_instance.nat_instance.public_ip
}
