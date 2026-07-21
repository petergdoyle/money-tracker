FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create persistent data directory
RUN mkdir -p /app/data

EXPOSE 8220

HEALTHCHECK CMD curl --fail http://localhost:8220/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8220", "--server.address=0.0.0.0"]
