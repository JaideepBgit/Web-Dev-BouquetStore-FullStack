# Base image
FROM public.ecr.aws/bitnami/python:3.8.12-prod

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx unzip && \
    rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip

# Download images from S3 bucket
RUN mkdir -p /app/static/images && \
    aws s3 sync s3://webappicationproject /app/static/images

WORKDIR /app

COPY requirements.txt /
RUN pip install -r /requirements.txt

# Install Gunicorn
RUN pip install gunicorn

COPY . .

# Run Gunicorn server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
