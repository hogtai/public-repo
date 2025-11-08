resource "aws_route_table" "project21_vpc_private_route_table1" {
  vpc_id = aws_vpc.project_21_vpc.id

  tags = {
    Name = "project21_vpc_private_route_table1"
  }
}

resource "aws_route_table" "project21_vpc_private_route_table2" {
  vpc_id = aws_vpc.project_21_vpc.id

  tags = {
    Name = "project21_vpc_private_route_table2"
  }
}

resource "aws_route_table_association" "private_subnet1_association" {
  subnet_id      = aws_subnet.private_subnet1_project21.id
  route_table_id = aws_route_table.project21_vpc_private_route_table1.id
}

resource "aws_route_table_association" "private_subnet2_association" {
  subnet_id      = aws_subnet.private_subnet2_project21.id
  route_table_id = aws_route_table.project21_vpc_private_route_table2.id
}
