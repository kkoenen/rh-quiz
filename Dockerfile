FROM python:3.12-slim

LABEL maintainer="RH Quiz App"
LABEL description="Red Hat Quiz Application"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY subjects.yaml .
COPY .env* ./

# Create data directory
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
