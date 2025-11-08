resource "aws_security_group" "db_tier_sg" {
  name        = var.db_tier_sg_name
  description = var.db_tier_sg_description
  vpc_id      = aws_vpc.project_21_vpc.id

  ingress {
    from_port       = var.db_tier_sg_web_ingress_from_port
    to_port         = var.db_tier_sg_web_ingress_to_port
    protocol        = var.db_tier_sg_web_ingress_protocol
    security_groups = [aws_security_group.project21_webtier_sg.id]
  }

  ingress {
    from_port   = var.db_tier_sg_ssh_ingress_from_port
    to_port     = var.db_tier_sg_ssh_ingress_to_port
    protocol    = var.db_tier_sg_ssh_ingress_protocol
    cidr_blocks = var.db_tier_sg_ssh_ingress_cidr_blocks
  }

  egress {
    from_port   = var.db_tier_sg_egress_from_port
    to_port     = var.db_tier_sg_egress_to_port
    protocol    = var.db_tier_sg_egress_protocol
    cidr_blocks = var.db_tier_sg_egress_cidr_blocks
  }

  tags = {
    Name = var.db_tier_sg_name
  }
}

