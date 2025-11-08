# Two Public && Two Private Subnets
resource "aws_subnet" "public_subnet1_project21" {
  vpc_id            = aws_vpc.project_21_vpc.id
  cidr_block        = var.public_subnet1_cidr_block
  availability_zone = var.availability_zone_a

  tags = {
    Name = var.public_subnet1_name_tag
  }
}

resource "aws_subnet" "public_subnet2_project21" {
  vpc_id            = aws_vpc.project_21_vpc.id
  cidr_block        = var.public_subnet2_cidr_block
  availability_zone = var.availability_zone_b

  tags = {
    Name = var.public_subnet2_name_tag
  }
}

resource "aws_subnet" "private_subnet1_project21" {
  vpc_id            = aws_vpc.project_21_vpc.id
  cidr_block        = var.private_subnet1_cidr_block
  availability_zone = var.availability_zone_a

  tags = {
    Name = var.private_subnet1_name_tag
  }
}

resource "aws_subnet" "private_subnet2_project21" {
  vpc_id            = aws_vpc.project_21_vpc.id
  cidr_block        = var.private_subnet2_cidr_block
  availability_zone = var.availability_zone_b

  tags = {
    Name = var.private_subnet2_name_tag
  }
}
