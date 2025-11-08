provider "aws" {
  region = "us-east-2"
}

resource "aws_vpc" "project_21_vpc" {
  cidr_block       = "10.10.0.0/16"
  instance_tenancy = "default"

  tags = {
    Name = "Project_21-Terraform"
  }
}

resource "aws_internet_gateway" "project_21_internet_gateway" {
  vpc_id = aws_vpc.project_21_vpc.id

  tags = {
    Name = "project_21_internet_gateway"
  }
}
