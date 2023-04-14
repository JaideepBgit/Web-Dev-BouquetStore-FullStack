# Base image
FROM public.ecr.aws/bitnami/python:3.8.12-prod

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /
RUN pip install -r /requirements.txt

# Install Gunicorn
RUN pip install gunicorn

COPY . .

# Run Gunicorn server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
