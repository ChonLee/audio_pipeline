FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy main Python files from root
COPY main.py processor.py requirements.txt .  

# Copy app contents (not the folder itself)
COPY app ./app
COPY assets/ ./assets

# Create an empty config folder inside the container
RUN mkdir -p config

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for Flask
EXPOSE 5000

# Run Flask app
CMD ["python", "main.py"]
