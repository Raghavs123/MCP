"""Entry point named in the project brief:

    python agent.py "What does my note on RAG say about chunk size?"

Uses MCP_AGENT_PROVIDER (gemini | local | fake, default gemini) and MCP_AGENT_MODEL from .env.
The loop lives in src/mcpagent/agent.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mcpagent.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["ask", *sys.argv[1:]]))
