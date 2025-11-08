#!/bin/bash

# Set the MySQL credentials
MYSQL_USER="your_username"
MYSQL_PASSWORD="your_password"
MYSQL_HOST="localhost"
MYSQL_DATABASE="your_database"

# Get the current date and time in Central time zone
CURRENT_TIME=$(TZ="America/Chicago" date +"%H:%M")

# Check if it's 7:00 PM Central time
if [ "$CURRENT_TIME" = "19:00" ]; then
    # Build the MySQL query
    QUERY="SELECT * FROM your_table;"

    # Execute the query and save the result to a file
    mysql -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -h "$MYSQL_HOST" -D "$MYSQL_DATABASE" -e "$QUERY" > result.txt

    # Check if the query execution was successful
    if [ $? -eq 0 ]; then
        echo "MySQL query executed successfully."
    else
        echo "Error executing MySQL query."
    fi
else
    echo "Not yet time to execute the MySQL query."
fi
