FROM python:3.12-slim

# Set the API key as an environment variable
ARG OPENROUTER_API_KEY
ENV OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
ARG GH_PAT
ENV GH_PAT=${GH_PAT}
ARG WGB_TABLE
ENV WGB_TABLE=${WGB_TABLE}
ARG WGB_BUCKET
ENV WGB_BUCKET=${WGB_BUCKET}
ARG WGB_GH_ACTION_URL
ENV WGB_GH_ACTION_URL=${WGB_GH_ACTION_URL}


# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends build-essential

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Remove build dependencies
RUN apt-get purge -y --auto-remove build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

CMD ["python", "-m", "src.eval"]
