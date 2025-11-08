resource "aws_security_group" "postgres_security_group" {
  name        = var.security_group_name
  description = var.security_group_description

  ingress {
    from_port   = var.inbound_port1
    to_port     = var.inbound_port1
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

