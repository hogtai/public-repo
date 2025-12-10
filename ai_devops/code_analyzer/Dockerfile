# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the application directory contents into the container at /app
COPY app/ /app/

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
# Use --default-timeout=100 to prevent timeouts during install
RUN pip install --no-cache-dir --default-timeout=100 -r /app/requirements.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable
ENV PORT 8080
ENV PYTHONUNBUFFERED TRUE

# Run main.py when the container launches using gunicorn
# Assumes your Flask app instance is named 'app' in main.py
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "290", "main:app"]
