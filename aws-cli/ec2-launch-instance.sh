aws ec2 run-instances /
--image-id ami-0b5eea76982371e91 /
--count 1 --instance-type t2.micro /
--key-name AWS_CDA_SERVER_KEYPAIR /
--security-group-ids sg-0bf5df57404d2ada9 /
--subnet-id subnet-02105e7ee200e6cf5 /
--associate-public-ip-address /
