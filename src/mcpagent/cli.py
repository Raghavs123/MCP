"""Command line:  mcpagent <command>   (or  python -m mcpagent <command>)

ask "question"   one question through the agent (prints the tools it used and the answer)
tools            start the server with the MCP SDK client and list its tools
raw-check        talk to the server with a hand-written JSON-RPC client (no MCP SDK)
eval             run tasks.jsonl, save results/<label>.json (resumable)
report           rebuild reports/RESULTS.md from every results/*.json (no model calls)
serve            run the server over streamable HTTP (remote use)

Settings come from environment variables or .env:
  MCP_AGENT_PROVIDER = gemini | local | fake   (default gemini, as in the project brief)
  MCP_AGENT_MODEL    = small | big | <model id> (default big)
  MCP_AGENT_SLEEP_S  = pause after each eval task (free-tier rate limits)
  MCP_SEARCH_MODE    = words | phrase           (how search_notes matches; default words = v2)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys

from dotenv import load_dotenv

from mcpagent.agent import ROOT, ask, server_params

load_dotenv(ROOT / ".env")


def _model(args):
    from mcpagent.llm import build_model

    provider = args.provider or os.environ.get("MCP_AGENT_PROVIDER", "gemini")
    return build_model(provider, args.model or os.environ.get("MCP_AGENT_MODEL")), provider


def label_for(provider: str, model) -> str:
    """Run label, e.g. local-cuda__qwen2.5-3b-instruct__search-words. CPU and GPU never mix."""
    short = re.sub(r"[^a-z0-9.]+", "-", model.name.lower().split("/")[-1]).strip("-")
    device = getattr(model, "device", "")
    where = f"{provider}-{device}" if device and device != "cpu" else provider
    return f"{where}__{short}__search-{os.environ.get('MCP_SEARCH_MODE', 'words')}"


def cmd_ask(args) -> int:
    model, _ = _model(args)
    res = asyncio.run(ask(args.question, model))
    for use in res.tools_used:
        print(f"tool  : {use.name}({json.dumps(use.arguments, ensure_ascii=False)})  {use.seconds:.2f}s")
    print(f"answer: {res.answer}")
    print(
        f"time  : {res.seconds:.1f}s total ({res.llm_seconds:.1f}s model, {res.tool_seconds:.2f}s tools, "
        f"{res.steps} model calls)"
    )
    return 0


def cmd_tools(args) -> int:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    async def run():
        async with stdio_client(server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                print(f"server: {init.serverInfo.name}  protocol {init.protocolVersion}")
                for t in (await session.list_tools()).tools:
                    params = ", ".join(t.inputSchema.get("properties", {}))
                    print(f"- {t.name}({params}): {t.description.splitlines()[0]}")

    asyncio.run(run())
    return 0


def cmd_raw_check(args) -> int:
    from mcpagent.raw_client import handshake_and_call

    out = handshake_and_call(ROOT / "server.py", "search_notes", {"query": args.query})
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


def cmd_eval(args) -> int:
    from mcpagent.evaluation import load_tasks, run_eval

    model, provider = _model(args)
    tasks = load_tasks(ROOT / "tasks.jsonl")[: args.limit or None]
    out = ROOT / "results" / f"{label_for(provider, model)}.json"
    sleep_s = float(os.environ.get("MCP_AGENT_SLEEP_S", "0"))
    asyncio.run(run_eval(model, tasks, out, sleep_s=sleep_s))
    return cmd_report(args)


def cmd_report(args) -> int:
    from mcpagent.report import write_report

    path, rows = write_report(ROOT)
    for r in rows:
        print(
            f"{r['label']:55s} right tool {r['right_tool_first']}/{r['n']}  "
            f"answer correct {r['answer_correct']}/{r['n']}  avg {r['avg_seconds']}s"
        )
    print(f"wrote {path}")
    return 0


def cmd_serve(args) -> int:
    from mcpagent.server import main as serve

    serve(["--http", "--port", str(args.port)])
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="mcpagent", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--provider", choices=["gemini", "local", "fake"])
    common.add_argument("--model", help="small | big | a model id")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask", parents=[common], help="ask one question")
    a.add_argument("question")
    a.set_defaults(func=cmd_ask)
    sub.add_parser("tools", help="list the server's tools").set_defaults(func=cmd_tools)
    r = sub.add_parser("raw-check", help="hand-written JSON-RPC client")
    r.add_argument("--query", default="chunk size")
    r.set_defaults(func=cmd_raw_check)
    e = sub.add_parser("eval", parents=[common], help="run tasks.jsonl")
    e.add_argument("--limit", type=int, default=0)
    e.set_defaults(func=cmd_eval)
    sub.add_parser("report", help="rebuild reports/RESULTS.md").set_defaults(func=cmd_report)
    s = sub.add_parser("serve", help="streamable HTTP server")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
