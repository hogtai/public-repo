resource "aws_subnet" "public_subnet1_project21" {
  vpc_id            = aws_vpc.project_21_vpc.id
  cidr_block        = "10.10.1.0/24"
  availability_zone = "us-east-2a"

  tags = {
    Name = "public_subnet1_project21"
  }
}

resource "aws_subnet" "public_subnet2_project21" {
  vpc_id            = aws_vpc.project_21_vpc.id
  cidr_block        = "10.10.2.0/24"
  availability_zone = "us-east-2b"

  tags = {
    Name = "public_subnet2_project21"
  }
}

resource "aws_subnet" "private_subnet1_project21" {
  vpc_id            = aws_vpc.project_21_vpc.id
  cidr_block        = "10.10.3.0/24"
  availability_zone = "us-east-2a"

  tags = {
    Name = "private_subnet1_project21"
  }
}

resource "aws_subnet" "private_subnet2_project21" {
  vpc_id            = aws_vpc.project_21_vpc.id
  cidr_block        = "10.10.4.0/24"
  availability_zone = "us-east-2b"

  tags = {
    Name = "private_subnet2_project21"
  }
}
