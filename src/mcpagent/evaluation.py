"""Measure the agent on tasks.jsonl: did it pick the right tool, and was the answer correct?

* right tool (first)  - the FIRST tool the model called is the expected one (strict)
* right tool (any)    - the expected tool was called at some point (lenient)
* answer correct      - automatic check: the answer contains one of the expected strings,
                        or (write tasks) the note file really exists and contains the text.

Every task result is saved to results/<label>.json as soon as it is done, so a run that hits
a free-tier limit can simply be started again: finished tasks are skipped.
The notes folder is copied to a temporary folder first, so write_note never changes notes/.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from mcpagent.agent import ROOT, run_agent, server_params
from mcpagent.llm.base import ChatModel
from mcpagent.tools import SLUG_RE, write_note


def load_tasks(path: Path) -> list[dict]:
    tasks = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task ids")
    return tasks


def check_answer(task: dict, answer: str, notes_dir: Path) -> bool:
    if "note_contains" in task:
        want = task["note_contains"]
        f = notes_dir / (SLUG_RE.sub("-", want["title"].lower()).strip("-") + ".md")
        return f.exists() and want["text"].lower() in f.read_text(encoding="utf-8").lower()
    return any(s.lower() in (answer or "").lower() for s in task["answer_contains_any"])


def score(task: dict, result: dict, notes_dir: Path) -> dict:
    names = [t["name"] for t in result["tools_used"]]
    return {
        "right_tool_first": bool(names) and names[0] == task["tool"],
        "right_tool_any": task["tool"] in names,
        "answer_correct": check_answer(task, result["answer"], notes_dir),
        "tools_called": names,
    }


def load_results(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}


def save_results(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes((json.dumps(data, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    tmp.replace(path)


async def run_eval(model: ChatModel, tasks: list[dict], out: Path, sleep_s: float = 0.0, log=print) -> dict:
    data = load_results(out)
    todo = [t for t in tasks if t["id"] not in data]
    log(f"{out.name}: {len(data)} done, {len(todo)} to run")
    if not todo:
        return data
    with tempfile.TemporaryDirectory() as tmp:
        notes = Path(tmp) / "notes"
        shutil.copytree(ROOT / "notes", notes)
        for t in data.values():  # notes written by an earlier (resumed) run
            for use in t["result"]["tools_used"]:
                if use["name"] == "write_note":
                    write_note(use["arguments"].get("title", ""), use["arguments"].get("text", ""), notes)
        async with stdio_client(server_params(notes)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for task in todo:
                    result = (await run_agent(task["question"], model, session)).to_dict()
                    data[task["id"]] = {"task": task, "result": result, **score(task, result, notes)}
                    save_results(out, data)
                    s = data[task["id"]]
                    log(
                        f"  {task['id']:3s} tools={s['tools_called']} first_ok={s['right_tool_first']} "
                        f"answer_ok={s['answer_correct']} {result['seconds']:.1f}s"
                    )
                    if sleep_s:
                        time.sleep(sleep_s)  # free-tier rate limit; not part of the measured time
    return data


def summarize(label: str, data: dict, tasks: list[dict]) -> dict:
    rows = [data[t["id"]] for t in tasks if t["id"] in data]
    n = len(rows)

    def mean(key):
        return round(sum(r["result"][key] for r in rows) / n, 2) if n else 0.0

    by_tool = {}
    for r in rows:
        tool = r["task"]["tool"]
        ok, tot = by_tool.get(tool, (0, 0))
        by_tool[tool] = (ok + r["right_tool_first"], tot + 1)
    return {
        "label": label,
        "n": n,
        "right_tool_first": sum(r["right_tool_first"] for r in rows),
        "right_tool_any": sum(r["right_tool_any"] for r in rows),
        "answer_correct": sum(r["answer_correct"] for r in rows),
        "stopped": sum(r["result"]["stopped"] for r in rows),
        "avg_steps": mean("steps"),
        "avg_seconds": mean("seconds"),
        "avg_llm_seconds": mean("llm_seconds"),
        "avg_tool_seconds": mean("tool_seconds"),
        "avg_input_tokens": mean("input_tokens"),
        "by_tool": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_tool.items())},
    }
