# Use Python 3.10 as base image
FROM python:3.10-slim

# Add useful command line tools and gosu for step-down from root
RUN apt-get update && \
    apt-get install -y curl wget git jq zip unzip rsync tree telnet netcat-traditional gosu file bind9-host bind9-dnsutils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .


COPY docker-entrypoint.sh /usr/local/bin/
COPY setup_ssh_keys.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/setup_ssh_keys.sh

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=8000
ENV WORKDIR=/home/projects
# Default UID/GID (can be overridden at runtime)
ENV UID=1000
ENV GID=1000

# Create directory for projects
RUN mkdir -p /home/projects

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "server.py"]

