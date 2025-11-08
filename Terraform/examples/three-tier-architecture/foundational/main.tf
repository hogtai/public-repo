provider "aws" {
  region = "us-east-2"
}

resource "aws_instance" "example" {
  ami           = "ami-0533def491c57d991"
  instance_type = "t2.micro"
}