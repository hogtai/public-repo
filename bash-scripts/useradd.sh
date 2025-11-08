#!/bin/bash
# Script used to auto add a user to the server by: Tait Hoglund

if [ $(id -u) -eq 0 ]; then
        read -p "Select a Username : " username
        read -s -p "Set your Password : " password
        egrep "^$username" /etc/passwd > /dev/null
                if [ $? -eq 0 ]; then
                                echo "$username already exists. Please choose a different username."
                                exit 1
                        else
                                pass=$(perl -e 'print crypt($ARGV[0], "password")' $password)
                                useradd -m -p $pass $username
                                [ $? -eq 0 ] && echo "You have been successfully added to the system" || echo "Authentication Error. Failed to Create New User"
                        fi
                else
                        echo "Only a user with administrative privledges may add a user to the system."
                        exit 2
                fi
