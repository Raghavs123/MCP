# 3-day build roadmap (easy language)

Goal: build a small **MCP server** with tools, an **agent** that uses it, prove the same server
works in **any MCP client**, and **measure** how often the agent picks the right tool.

Think of a power socket. MCP is the socket shape: once your tools fit the socket, any device
(Claude Desktop, an IDE, your own agent) can plug in, and you never rewire the house.

```
mcp-agent/
├── server.py, agent.py        the brief's entry points (python server.py / python agent.py "...")
├── notes/                     8 markdown notes the search tool reads
├── tasks.jsonl                15 test tasks, each with the tool it should use
├── claude_desktop_config.example.json
├── src/mcpagent/
│   ├── tools.py               search_notes, read_github_file, write_note as plain functions
│   ├── server.py              the MCP server (FastMCP): stdio or streamable HTTP
│   ├── llm/                   gemini (brief), local Qwen (no key), fake (tests)
│   ├── agent.py               the loop: model -> tool -> model, max 5 steps
│   ├── raw_client.py          a second client: JSON-RPC by hand, no MCP SDK
│   ├── evaluation.py, report.py   the measurement
│   └── cli.py                 mcpagent ask | tools | raw-check | eval | report | serve
├── tests/                     offline tests over the real protocol
├── results/, reports/         the evidence and the tables
└── docs/                      this roadmap + demo.gif
```

## Day 1 - the server (about 4 hours)
1. **Setup (30 min).** venv, `pip install -e ".[dev]"` (MCP SDK pinned below 2: version 2 renames
   FastMCP to MCPServer). Free Gemini key from Google AI Studio into `.env`.
2. **Notes (20 min).** Write 5-10 short notes in `notes/`, each with facts you can ask about.
3. **Tools as plain functions (60 min) - `tools.py`.** Easy to test without MCP. Add safety from
   the start: check the repo name, refuse `..` in paths, never let `write_note` leave the folder
   or overwrite a note.
4. **The server (30 min) - `server.py`.** `@mcp.tool()` turns each function into an MCP tool;
   the docstring becomes the description the model reads. Never `print()` in a stdio server.
5. **Test the server alone (30 min).** `mcpagent tools` (SDK client) and `mcpagent raw-check`
   (JSON-RPC by hand). The MCP Inspector (`mcp dev server.py`, needs Node.js) is the visual way.
6. **Tests (60 min).** `pytest`: tools, the protocol in memory, and the real stdio server.

## Day 2 - the agent and the measurement (about 5 hours)
7. **Model clients (60 min) - `llm/`.** One interface: `chat(messages, tools)`. Gemini through its
   OpenAI-compatible endpoint; a local Qwen model if you have no key; a fake one for tests.
8. **The agent loop (60 min) - `agent.py`.** List the server's tools, turn them into function
   definitions, loop at most 5 times.
9. **15 tasks (45 min) - `tasks.jsonl`.** 7 notes, 6 GitHub, 2 write-note questions, each with the
   expected tool and a way to check the answer automatically. GitHub facts must be inside the
   first 6000 characters, because that is all the tool returns.
10. **Run it (waiting).** `mcpagent eval`. On a free tier set `MCP_AGENT_SLEEP_S=4`; a stopped run
    resumes. Read every answer once yourself: the automatic check can be fooled.

## Day 3 - portability, improvement, shipping (about 4 hours)
11. **Claude Desktop (30 min).** Add the server to `claude_desktop_config.json`
    (see `claude_desktop_config.example.json`), restart, ask the same questions, record 20 s.
12. **Improve once.** Look at the failed tasks. Change one thing (a tool description, the search
    rule, the system prompt), run again, and keep both rows in the README.
13. **Ship.** README (one sentence + GIF, diagram, 3 commands, results, what failed, what next),
    CI, Dockerfile (streamable HTTP), push, pin the repo.
