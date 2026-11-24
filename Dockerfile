# Template - not built while making this repo (no Docker on the build machine).
# Runs the MCP server over streamable HTTP, so a remote client can use it:
#   docker build -t mcp-agent .
#   docker run -p 8000:8000 mcp-agent        ->  MCP endpoint http://localhost:8000/mcp
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY server.py ./
COPY notes ./notes
RUN pip install . && useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
# Listen on all interfaces inside the container (the default 127.0.0.1 is unreachable from outside)
CMD ["python", "-c", "from mcpagent.server import mcp; mcp.settings.host='0.0.0.0'; mcp.run(transport='streamable-http')"]
