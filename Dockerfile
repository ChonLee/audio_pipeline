FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy main Python files from root
COPY main.py processor.py .  

# Copy app subfolders
COPY app/ ./app  
COPY config/ ./config
COPY assets/ ./assets

# Copy Python dependencies
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Run Flask app
CMD ["python", "main.py"]
