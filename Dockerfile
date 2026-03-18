# Use a slim Python image for a smaller footprint
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# We include 'build-essential' just in case numpy/pandas need to compile 
# and 'curl' for health checks.
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port Flask runs on
EXPOSE 5000

# Set environment variables for Flask
ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

# Start the Flask application
CMD ["flask", "run"]