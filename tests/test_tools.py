import httpx
import pytest

from mcpagent import tools


@pytest.fixture
def notes(tmp_path):
    (tmp_path / "rag.md").write_text("# RAG\n- Chunk size: start with about 500 tokens.\n", encoding="utf-8")
    (tmp_path / "git.md").write_text("# Git\n- Never commit .env files.\n", encoding="utf-8")
    return tmp_path


def test_search_finds_a_phrase_with_the_file_name(notes):
    assert (
        tools.search_notes("chunk size", notes, "phrase")
        == "rag.md: - Chunk size: start with about 500 tokens."
    )


def test_phrase_mode_misses_reordered_words_but_words_mode_finds_them(notes):
    assert tools.search_notes("size of chunk", notes, "phrase") == "No matches."
    assert "500 tokens" in tools.search_notes("size of chunk", notes, "words")


def test_search_is_case_insensitive_and_says_no_matches(notes):
    assert "git.md" in tools.search_notes("NEVER COMMIT", notes, "phrase")
    assert tools.search_notes("kubernetes", notes, "phrase") == "No matches."


def test_write_note_saves_inside_the_folder_and_never_overwrites(notes):
    assert tools.write_note("Stand-up!", "Finish by Friday.", notes) == "Saved stand-up.md."
    assert "Friday" in (notes / "stand-up.md").read_text(encoding="utf-8")
    assert tools.write_note("stand up", "again", notes).startswith("Error: a note called")


def test_write_note_cannot_escape_the_folder(notes):
    assert tools.write_note("../../evil", "x", notes) == "Saved evil.md."
    assert (notes / "evil.md").exists()
    assert tools.write_note("!!!", "x", notes).startswith("Error")


def _client(status=200, text="# Title\n" + "x" * 9000):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(status, text=text)

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_read_github_file_builds_the_raw_url_and_truncates():
    client, seen = _client()
    out = tools.read_github_file("rasbt/LLMs-from-scratch", "README.md", client)
    assert seen == ["https://raw.githubusercontent.com/rasbt/LLMs-from-scratch/HEAD/README.md"]
    assert out.startswith("# Title") and len(out) == tools.MAX_CHARS


def test_read_github_file_reports_http_errors():
    client, _ = _client(status=404, text="nope")
    assert tools.read_github_file("a/b", "missing.md", client) == "Error 404"


@pytest.mark.parametrize("repo", ["not a repo", "a/b/c", "https://github.com/a/b"])
def test_read_github_file_rejects_bad_repo_names(repo):
    assert tools.read_github_file(repo).startswith("Error: repo")


def test_read_github_file_rejects_parent_paths():
    assert tools.read_github_file("a/b", "../secrets").startswith("Error: path")


def test_words_mode_ranks_lines_and_counts_the_file_name(notes):
    # "rag" is only in the file name, "chunk size" only in the line: v1 finds nothing
    assert tools.search_notes("rag chunk size", notes, "phrase") == "No matches."
    first = tools.search_notes("rag chunk size", notes, "words").splitlines()[0]
    assert first == "rag.md: - Chunk size: start with about 500 tokens."


def test_words_mode_matches_plurals_and_skips_headings(notes):
    (notes / "mcp.md").write_text("# MCP\n- Transports: stdio for local servers.\n", encoding="utf-8")
    assert (
        tools.search_notes("MCP server", notes, "words") == "mcp.md: - Transports: stdio for local servers."
    )
