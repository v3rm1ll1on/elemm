# ==============================================================================
# STAGE 1: Build the React Frontend
# ==============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy package files first for cache efficiency
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source code and build for production
COPY frontend/ ./
RUN npm run build

# ==============================================================================
# STAGE 2: Package and Run the Python Backend
# ==============================================================================
FROM python:3.12-slim AS runner
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy the built frontend assets from STAGE 1
COPY --from=frontend-builder /app/frontend/dist /app/src/elemm_gateway/ui_backend/dist

# Copy the Python package files
COPY pyproject.toml MANIFEST.in ./
COPY src/ ./src/

# Install the Python package
RUN pip install --no-cache-dir .[fastapi]

# Create volume target for persisted configurations (secrets vault & security policy)
RUN mkdir -p /root/.elemm
VOLUME ["/root/.elemm"]

# Expose ports:
# - 8090: The dashboard / dashboard API
# - 8000: Default MCP Gateway SSE endpoint
EXPOSE 8090 8000

# Set environment variables for FastAPI / Uvicorn
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0

# Copy the entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Start both services via the entrypoint script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
