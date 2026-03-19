data "aws_ami" "amzn2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_security_group" "db_debug_sg" {
  count = var.enable_debug_instance ? 1 : 0

  name        = "code-quality-db-debug-sg"
  description = "SSH access for temporary DB debugging host"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "db_debug" {
  count = var.enable_debug_instance ? 1 : 0

  ami                         = data.aws_ami.amzn2.id
  instance_type               = var.debug_instance_type
  subnet_id                   = module.vpc.public_subnets[0]
  vpc_security_group_ids      = [aws_security_group.db_debug_sg[0].id]
  key_name                    = var.debug_key_name
  associate_public_ip_address = true

  user_data = <<-EOT
              #!/bin/bash
              set -euxo pipefail
              yum update -y
              yum install -y postgresql15 || yum install -y postgresql
              EOT

  tags = {
    Name = "code-quality-db-debug"
  }
}
