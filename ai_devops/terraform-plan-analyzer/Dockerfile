FROM python:3.12-slim-bookworm

# Install minimal required packages and clean up cache
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create empty directory structure
RUN mkdir -p /app
WORKDIR /app

# Copy files individually to prevent overwriting issues
COPY app/* /app/

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]