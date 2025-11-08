# Set up the AWS provider and the region we'll be using
provider "aws" {
  region = var.aws_region
}

# Define a new VPC resource
resource "aws_vpc" "project_21_vpc" {

  # Specify the CIDR block for the VPC
  cidr_block = var.vpc_cidr_block

  # Use the default tenancy setting for the VPC
  instance_tenancy = var.vpc_instance_tenancy

  # Assign a name tag to the VPC
  tags = {
    Name = var.vpc_name_tag
  }
}

# Create an Internet Gateway resource and attach it to the VPC
resource "aws_internet_gateway" "project_21_internet_gateway" {

  # Use the ID of the VPC we just created
  vpc_id = aws_vpc.project_21_vpc.id

  # Assign a name tag to the Internet Gateway
  tags = {
    Name = var.internet_gateway_name_tag
  }
}
