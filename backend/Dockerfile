FROM python:3.11-slim

WORKDIR /app

# System deps for Silero VAD (torch) and bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent database volume mount point
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "server.py"]
