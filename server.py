"""Entry point named in the project brief:  python server.py   (stdio)   |   python server.py --http

Works without installing the package (it adds src/ to the path), so Claude Desktop can start it
with an absolute path. The tools live in src/mcpagent/tools.py, the server in src/mcpagent/server.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mcpagent.server import main  # noqa: E402

if __name__ == "__main__":
    main()
