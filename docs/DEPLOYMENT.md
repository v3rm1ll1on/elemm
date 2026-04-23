# Elemm Deployment: Docker and Cloud Infrastructure

Deploying landmark-enabled APIs requires attention to how proxies handle long-lived connections, especially when using the Model Context Protocol over SSE (Server-Sent Events).

## 1. Dockerization

### 1.1 Native Python (No Framework)

A pure Python MCP server (e.g., using `run_mcp_stdio` or the `mcp` CLI) doesn't need to expose network ports:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install elemm

COPY . .

# Run via stdio (The container runs indefinitely waiting for MCP stdin)
CMD ["python", "my_module.py"]
```

### 1.2 FastAPI Integration (SSE)

A standard FastAPI deployment with Elemm (using SSE):

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install elemm

COPY . .

# Run the API. Note: SSE works best with workers=1 per container 
# to ensure session stickiness if not using an external session store.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 2. Nginx Configuration

When using Nginx as a reverse proxy, you must disable buffering for SSE to work correctly. Otherwise, the agent will experience significant lag or timeouts.

```nginx
server {
    listen 80;
    server_name api.solar-ops.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # SSE Specific Tuning
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 24h;
        
        # Force no-buffer for Elemm/MCP responses
        add_header X-Accel-Buffering no;
    }
}
```

## 3. Cloud Load Balancers (AWS/GCP/Azure)

- **AWS ALB**: Ensure "Sticky Sessions" are enabled if you are running multiple pods/containers, as the LandmarkBridge context is stored in-memory (per session).
- **GCP Global LB**: Set the "Response Timeout" to a high value (e.g., 3600 seconds) to prevent the load balancer from closing the SSE stream prematurely.
- **Azure App Service**: Enable "Web Sockets" (which often shares the same underlying pipe logic as SSE) to ensure stable long-polling or streaming.

## 4. Root Path Support

If your API is served behind a path (e.g., `https://company.com/api/v1/`), ensure you initialize FastAPI with the correct `root_path`:

```python
app = FastAPI(root_path="/api/v1")
ai.bind_mcp_sse(app, route_prefix="/mcp")
```

Elemm automatically detects the `root_path` and adjusts the SSE and manifest URLs accordingly.
