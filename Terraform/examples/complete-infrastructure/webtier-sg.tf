resource "aws_security_group" "project21_webtier_sg" {
  name        = var.sg_name
  description = var.sg_description
  vpc_id      = aws_vpc.project_21_vpc.id

  dynamic "ingress" {
    for_each = var.sg_ingress_ports
    content {
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.protocol == "tcp" && ingress.value.from_port == 22 ? var.sg_ssh_cidr_blocks : ["0.0.0.0/0"]
    }
  }

  egress {
    from_port   = var.sg_egress_rule.from_port
    to_port     = var.sg_egress_rule.to_port
    protocol    = var.sg_egress_rule.protocol
    cidr_blocks = var.sg_egress_rule.cidr_blocks
  }

  tags = var.sg_tags
}
