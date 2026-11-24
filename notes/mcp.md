# MCP (Model Context Protocol)

- Three roles: host (the app), client (one per server), server (exposes tools).
- A server can expose tools, resources and prompts.
- Transports: stdio for local servers, streamable HTTP for remote servers.
- Never use print() in a stdio server: stdout carries the protocol. Log to stderr.
- One server works in any MCP client: Claude Desktop, IDEs, your own agent.
