"""Run the brief's two example questions for real and save what the terminal showed.

    python scripts/record_demo.py      -> reports/demo_output.txt
    python scripts/make_demo_gif.py    -> docs/demo.gif (animation of that text, not a screen capture)

Uses MCP_AGENT_PROVIDER / MCP_AGENT_MODEL from .env (or the environment).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = [
    "What does my note on RAG say about chunk size?",
    "Summarise the README of rasbt/LLMs-from-scratch in one sentence.",
]


def main() -> int:
    lines = []
    for q in QUESTIONS:
        cmd = [sys.executable, "agent.py", q]
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True)
        lines += [f'$ python agent.py "{q}"', *out.stdout.splitlines(), ""]
    path = ROOT / "reports" / "demo_output.txt"
    path.write_bytes("\n".join(lines).encode("utf-8"))
    print(path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
