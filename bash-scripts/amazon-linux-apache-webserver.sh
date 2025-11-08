!#/bin/bash

# Update and Upgrade Amazon Linux Packages

yum -y update
yum -y upgrade

## Apache Web Server Install and Start

yum install -y httpd
systemctl start httpd
systemctl status httpd

# Amazon Web Server Stress Test Utility Tool Install and Start

amazon-linux-extras install epel -y
yum install stress -y
