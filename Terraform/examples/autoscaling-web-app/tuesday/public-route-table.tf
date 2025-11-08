resource "aws_route_table" "project21_vpc_public_route_table" {
  vpc_id = aws_vpc.project_21_vpc.id

  tags = {
    Name = "project21_vpc_public_route_table"
  }
}
