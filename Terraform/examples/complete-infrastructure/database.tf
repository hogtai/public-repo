resource "aws_db_subnet_group" "private_db_subnet_group" {
  name       = var.db_subnet_group_name
  subnet_ids = [aws_subnet.private_subnet1_project21.id, aws_subnet.private_subnet2_project21.id]

  tags = {
    Name = var.db_subnet_group_name
  }
}

resource "aws_rds_cluster" "aurora_mysql_cluster" {
  cluster_identifier           = var.db_cluster_identifier
  engine                       = "aurora-mysql"
  engine_version               = "5.7.mysql_aurora.2.07.2"
  database_name                = "MyDatabase"
  master_username              = var.db_master_username
  master_password              = var.db_master_password
  db_subnet_group_name         = aws_db_subnet_group.private_db_subnet_group.name
  vpc_security_group_ids       = [aws_security_group.db_tier_sg.id]
  availability_zones           = ["${var.aws_region}a", "${var.aws_region}b"]
  storage_encrypted            = true
  skip_final_snapshot          = true
  backup_retention_period      = 7
  preferred_backup_window      = "07:00-09:00"
  preferred_maintenance_window = "Sat:10:00-Sat:10:30"
  tags = {
    Terraform   = "true"
    Environment = "test"
  }

  provisioner "local-exec" {
    command = "echo 'db_host = \"${aws_rds_cluster.aurora_mysql_cluster.endpoint}\"' >> terraform.tfvars"
  }
}

resource "aws_rds_cluster_instance" "aurora_mysql_cluster_instance" {
  identifier          = "${var.db_cluster_identifier}-instance"
  cluster_identifier  = aws_rds_cluster.aurora_mysql_cluster.id
  instance_class      = var.db_instance_class
  engine              = "aurora-mysql"
  publicly_accessible = false
}