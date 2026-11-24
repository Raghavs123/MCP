import asyncio
import json

import pytest

from mcpagent.agent import ROOT, ask, mcp_tools_to_functions
from mcpagent.evaluation import check_answer, load_tasks, run_eval, score, summarize
from mcpagent.llm.base import ChatResult, ToolCall
from mcpagent.llm.fake import FakeModel
from mcpagent.llm.local import parse_tool_calls


def test_task_file_has_15_tasks_for_three_tools():
    tasks = load_tasks(ROOT / "tasks.jsonl")
    assert len(tasks) == 15
    assert {t["tool"] for t in tasks} == {"search_notes", "read_github_file", "write_note"}


def test_qwen_tool_call_parsing():
    text = 'Sure.\n<tool_call>\n{"name": "search_notes", "arguments": {"query": "rag"}}\n</tool_call>'
    calls, rest = parse_tool_calls(text)
    assert [(c.name, c.arguments) for c in calls] == [("search_notes", {"query": "rag"})]
    assert rest == "Sure."
    calls, rest = parse_tool_calls("<tool_call>{broken json}</tool_call> hello")
    assert calls == [] and rest == "hello"


def test_assistant_message_keeps_tool_calls_in_openai_format():
    msg = ChatResult("", [ToolCall("c1", "search_notes", {"query": "x"})]).as_message()
    assert msg["tool_calls"][0]["function"] == {"name": "search_notes", "arguments": '{"query": "x"}'}


def test_mcp_tools_become_function_definitions():
    class T:
        name, description, inputSchema = "t", "does t", {"type": "object", "properties": {}}

    assert mcp_tools_to_functions([T()]) == [
        {
            "type": "function",
            "function": {
                "name": "t",
                "description": "does t",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def test_agent_runs_end_to_end_through_the_real_stdio_server(tmp_path):
    (tmp_path / "rag.md").write_text("- Chunk size: 500 tokens\n", encoding="utf-8")
    res = asyncio.run(ask("What does my note on RAG say about chunk size?", FakeModel(), tmp_path))
    assert [u.name for u in res.tools_used] == ["search_notes"]
    assert "500" in res.answer and res.steps == 2 and not res.stopped


class Looper:
    """A model that never stops calling tools."""

    name = "looper"

    def chat(self, messages, tools):
        return ChatResult("", [ToolCall("c", "search_notes", {"query": "x"})])


def test_agent_stops_after_five_model_calls(tmp_path):
    res = asyncio.run(ask("loop forever", Looper(), tmp_path))
    assert res.stopped and res.steps == 5 and len(res.tools_used) == 5


@pytest.mark.parametrize(
    ("answer", "ok"), [("About 500 tokens.", True), ("I don't know.", False), (None, False)]
)
def test_answer_check(answer, ok, tmp_path):
    assert check_answer({"answer_contains_any": ["500"]}, answer, tmp_path) is ok


def test_note_check_reads_the_written_file(tmp_path):
    task = {"note_contains": {"title": "Stand up", "text": "friday"}}
    assert not check_answer(task, "done", tmp_path)
    (tmp_path / "stand-up.md").write_text("# Stand up\n\nFinish by Friday.\n", encoding="utf-8")
    assert check_answer(task, "done", tmp_path)


def test_score_separates_first_tool_from_any_tool(tmp_path):
    task = {"tool": "search_notes", "answer_contains_any": ["500"]}
    result = {"answer": "500", "tools_used": [{"name": "write_note"}, {"name": "search_notes"}]}
    s = score(task, result, tmp_path)
    assert (s["right_tool_first"], s["right_tool_any"], s["answer_correct"]) == (False, True, True)


def test_eval_is_resumable_and_never_changes_the_real_notes(tmp_path):
    tasks = [t for t in load_tasks(ROOT / "tasks.jsonl") if t["id"] in ("n1", "w1")]
    before = sorted(p.name for p in (ROOT / "notes").iterdir())
    out = tmp_path / "fake.json"
    model = FakeModel()
    data = asyncio.run(run_eval(model, tasks, out, log=lambda _m: None))
    calls = model.calls
    asyncio.run(run_eval(model, tasks, out, log=lambda _m: None))
    assert model.calls == calls  # nothing re-run
    assert sorted(p.name for p in (ROOT / "notes").iterdir()) == before
    assert data["w1"]["answer_correct"] and data["n1"]["right_tool_first"]
    s = summarize("fake", json.loads(out.read_text(encoding="utf-8")), tasks)
    assert (s["n"], s["right_tool_first"]) == (2, 2)
