"""The three tools as plain Python functions, so they can be tested without MCP or an LLM.

server.py wraps them as MCP tools. Each function returns a string, because that is what
a model reads back.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import httpx

GITHUB_RAW = "https://raw.githubusercontent.com"
MAX_CHARS = 6000  # a long README would fill the model's context: send the first 6000 characters
MAX_HITS = 15
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SLUG_RE = re.compile(r"[^a-z0-9-]+")


def notes_dir() -> Path:
    """Folder of markdown notes. MCP_NOTES_DIR lets the evaluation use a throw-away copy."""
    default = Path(__file__).resolve().parents[2] / "notes"
    return Path(os.environ.get("MCP_NOTES_DIR") or default)


def search_mode() -> str:
    """'phrase' = v1, the brief's rule: a line must contain the whole query.
    'words'  = v2: every query word of 3+ letters scores a point when it appears in the line or
               in the note's file name; lines are returned best first.
    v2 was added after the first measurement: models searched for 'rag chunk size' or
    'MCP server', phrases that never appear word for word in the notes."""
    return os.environ.get("MCP_SEARCH_MODE", "words")


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word  # servers -> server


def search_notes(query: str, folder: Path | None = None, mode: str | None = None) -> str:
    """Lines of the notes that match the query (case-insensitive), with file names."""
    folder = folder or notes_dir()
    mode = mode or search_mode()
    q = query.lower().strip()
    words = {_stem(w) for w in re.findall(r"[a-z0-9]+", q) if len(w) >= 3} if mode == "words" else set()
    scored = []
    for f in sorted(folder.glob("*.md")):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines()):
            if mode == "words" and (not line.strip() or line.startswith("#")):
                continue  # v2 skips headings: they match the file-name point on every query
            low = line.lower()
            whole = bool(q) and q in low
            points = sum(1 for w in words if w in low or w in f.stem.lower())
            if whole or points:
                scored.append((-(points + 10 * whole), f.name, n, f"{f.name}: {line.strip()}"))
    scored.sort()  # best first; ties keep file and line order
    return "\n".join(hit for *_, hit in scored[:MAX_HITS]) or "No matches."


def read_github_file(repo: str, path: str = "README.md", client: httpx.Client | None = None) -> str:
    """First 6000 characters of a file in a public GitHub repo, e.g. repo='rasbt/LLMs-from-scratch'."""
    repo, path = repo.strip(), path.strip().lstrip("/")
    if not REPO_RE.match(repo):
        return "Error: repo must look like 'owner/name'."
    if ".." in path.split("/"):
        return "Error: path must not contain '..'."
    url = f"{GITHUB_RAW}/{repo}/HEAD/{path}"
    try:
        if client is None:
            r = httpx.get(url, timeout=15, follow_redirects=True)
        else:
            r = client.get(url)
    except httpx.HTTPError as e:
        return f"Error: {type(e).__name__}"
    return r.text[:MAX_CHARS] if r.status_code == 200 else f"Error {r.status_code}"


def write_note(title: str, text: str, folder: Path | None = None) -> str:
    """Save a new markdown note. Never overwrites an existing note, never leaves the notes folder."""
    folder = folder or notes_dir()
    slug = SLUG_RE.sub("-", title.lower()).strip("-")[:60]
    if not slug:
        return "Error: the title needs at least one letter or digit."
    if len(text) > 5000:
        return "Error: the note is longer than 5000 characters."
    target = folder / f"{slug}.md"
    if target.exists():
        return f"Error: a note called {target.name} already exists."
    folder.mkdir(parents=True, exist_ok=True)
    target.write_bytes(f"# {title.strip()}\n\n{text.strip()}\n".encode())
    return f"Saved {target.name}."
