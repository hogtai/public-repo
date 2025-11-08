resource "aws_lb" "WebServerLoadBalancer" {
  name               = var.load_balancer_name
  internal           = var.load_balancer_internal
  load_balancer_type = var.load_balancer_type
  ip_address_type    = var.ip_address_type
  security_groups    = [aws_security_group.project21_webtier_sg.id]
  subnets            = [aws_subnet.public_subnet1_project21.id, aws_subnet.public_subnet2_project21.id]

  depends_on = [aws_security_group.project21_webtier_sg]
}

resource "aws_lb_listener" "webserver_lb_listener" {
  load_balancer_arn = aws_lb.WebServerLoadBalancer.arn
  port              = var.listener_port
  protocol          = var.listener_protocol

  default_action {
    type             = var.default_action_type
    target_group_arn = aws_lb_target_group.web_target_group.arn
  }
}
