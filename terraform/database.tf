resource "aws_security_group" "rds_sg" {
  name        = "code-quality-rds-sg"
  description = "Allow Postgres traffic from internal subnets"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks 
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "metadata_db" {
  identifier           = "code-quality-db"
  engine               = "postgres"
  engine_version       = "16.1"
  instance_class       = "db.t4g.micro"
  allocated_storage    = 20
  storage_type         = "gp3"
  
  db_name              = "codequality"
  username             = "postgres_admin"
  
  password             = var.db_password 

  db_subnet_group_name   = module.vpc.database_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  multi_az               = false
  publicly_accessible    = false
  skip_final_snapshot    = true
}