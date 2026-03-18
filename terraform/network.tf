data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.19.0"

  name = "code-quality-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["eu-central-1a", "eu-central-1b"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  database_subnets = ["10.0.21.0/24", "10.0.22.0/24"]

  enable_dns_hostnames = true
  enable_dns_support   = true
  enable_nat_gateway = false 
}

resource "aws_security_group" "nat_sg" {
  name        = "nat-instance-sg"
  description = "Allow traffic from private subnets to the internet"
  vpc_id      = module.vpc.vpc_id

  # Allow inbound traffic ONLY from your VPC private subnets
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }

  # Allow all outbound traffic to the internet
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_route" "private_nat_route_1" {
  route_table_id         = module.vpc.private_route_table_ids[0]
  destination_cidr_block = "0.0.0.0/0"
  instance_id            = aws_instance.nat_instance.id
}

resource "aws_route" "private_nat_route_2" {
  route_table_id         = module.vpc.private_route_table_ids[1]
  destination_cidr_block = "0.0.0.0/0"
  instance_id            = aws_instance.nat_instance.id
}


resource "aws_instance" "nat_instance" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t3.micro"
  subnet_id                   = module.vpc.public_subnets[0]
  associate_public_ip_address = true
  vpc_security_group_ids = [aws_security_group.nat_sg.id]
  source_dest_check    = false
  user_data = <<-EOF
    #!/bin/bash
    set -euxo pipefail

    dnf install -y iptables-services

    cat >/etc/sysctl.d/99-nat-forwarding.conf <<'SYSCTL'
    net.ipv4.ip_forward = 1
    SYSCTL
    sysctl --system

    OUT_IFACE=$(ip -o -4 route show to default | awk '{print $5; exit}')
    /sbin/iptables -t nat -A POSTROUTING -o "$OUT_IFACE" -j MASQUERADE
    /sbin/iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
    /sbin/iptables -A FORWARD -s 10.0.0.0/16 -j ACCEPT

    /sbin/iptables-save > /etc/sysconfig/iptables
    systemctl enable iptables
    systemctl restart iptables
  EOF

  tags = {
    Name = "cheap-nat-instance"
  }
}

resource "aws_eip" "nat_eip" {
  domain = "vpc"

  tags = {
    Name = "cheap-nat-eip"
  }
}

resource "aws_eip_association" "nat_eip_association" {
  allocation_id = aws_eip.nat_eip.id
  instance_id   = aws_instance.nat_instance.id
}