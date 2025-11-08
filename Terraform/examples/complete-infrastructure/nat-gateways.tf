resource "aws_eip" "nat_eip1" {
  domain = "vpc" # Update the argument from "vpc" to "domain"

  tags = {
    Name = var.nat_eip1_name_tag
  }
}

resource "aws_eip" "nat_eip2" {
  domain = "vpc" # Update the argument from "vpc" to "domain"

  tags = {
    Name = var.nat_eip2_name_tag
  }
}

