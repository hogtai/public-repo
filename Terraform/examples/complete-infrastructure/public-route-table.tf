resource "aws_route_table" "project21_vpc_public_route_table" {
  vpc_id = aws_vpc.project_21_vpc.id

  tags = {
    Name = var.public_route_table_name_tag
  }
}

resource "aws_route" "public_route_table_internet_gateway" {
  route_table_id         = aws_route_table.project21_vpc_public_route_table.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.project_21_internet_gateway.id
}

#Public Route Table Association
resource "aws_route_table_association" "public_subnet_association1" {
  subnet_id      = aws_subnet.public_subnet1_project21.id
  route_table_id = aws_route_table.project21_vpc_public_route_table.id
}