!#/bin/bash

sudo yum -y update

sudo yum -y upgrade

sudo yum install -y httpd

sudo systemctl start httpd

sudo systemctl status httpd
