resource "aws_lb" "WebServerLoadBalancer" {
  name               = "WebServerLoadBalancer"
  internal           = false
  load_balancer_type = "application"
  ip_address_type    = "ipv4"
  security_groups    = [aws_security_group.project21_webtier_sg.id]
  subnets            = [aws_subnet.public_subnet1_project21.id, aws_subnet.public_subnet2_project21.id]

  depends_on = [aws_security_group.project21_webtier_sg]
}

resource "aws_lb_listener" "webserver_lb_listener" {
  load_balancer_arn = aws_lb.WebServerLoadBalancer.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web_target_group.arn
  }
}