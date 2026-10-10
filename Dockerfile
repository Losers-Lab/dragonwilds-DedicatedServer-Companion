FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable immediate unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install ca-certificates, curl, and static docker client (sirhakon feature)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz \
        | tar -xz --strip-components=1 -C /usr/local/bin docker/docker \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

EXPOSE 9876

CMD ["python", "app.py"]
