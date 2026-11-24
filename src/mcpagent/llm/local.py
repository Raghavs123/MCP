"""Open Qwen2.5 models on your own computer, with real tool calling (no key, no quota).

Qwen2.5's chat template understands OpenAI-style tool definitions: the model answers with
<tool_call>{"name": ..., "arguments": {...}}</tool_call> blocks, which we parse into ToolCalls.
Greedy decoding: the same input always gives the same output.

The first run downloads the model (0.5B ~1 GB, 3B ~6 GB). Set HF_HOME to a disk with space.
Device: MCP_AGENT_DEVICE = cpu | cuda | auto (default auto: the GPU if PyTorch can see one).
Number format: float16 on a GPU; float32 on a CPU (the agent's prompts are long, and on a laptop
CPU without fast 16-bit maths, reading a long prompt was ~5x faster in float32).
"""

from __future__ import annotations

import json
import os
import re
import time

from mcpagent.llm.base import ChatResult, ToolCall

TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
SMALL, BIG = "Qwen/Qwen2.5-0.5B-Instruct", "Qwen/Qwen2.5-3B-Instruct"


class LocalModel:
    def __init__(
        self, name: str = BIG, dtype: str | None = None, device: str | None = None, max_new_tokens: int = 384
    ) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        threads = os.environ.get("MCP_AGENT_THREADS")
        if threads:
            torch.set_num_threads(int(threads))
        self.name = name
        self.max_new_tokens = max_new_tokens
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(name)
        device = device or os.environ.get("MCP_AGENT_DEVICE", "auto")
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        dtype = dtype or os.environ.get("MCP_AGENT_DTYPE") or ("float16" if device == "cuda" else "float32")
        self.model = AutoModelForCausalLM.from_pretrained(name, dtype=getattr(torch, dtype)).to(device).eval()
        self.chat([{"role": "user", "content": "Say OK."}], [])  # untimed warm-up

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatResult:
        start = time.perf_counter()
        ids = self.tokenizer.apply_chat_template(
            _for_template(messages),
            tools=tools or None,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        ).to(self.device)
        with self._torch.inference_mode():
            out = self.model.generate(
                **ids,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        new = out[0, ids["input_ids"].shape[1] :]
        text = self.tokenizer.decode(new, skip_special_tokens=True).strip()
        calls, content = parse_tool_calls(text)
        return ChatResult(
            content=content,
            tool_calls=calls,
            input_tokens=int(ids["input_ids"].shape[1]),
            output_tokens=int(len(new)),
            seconds=self._elapsed(start),
        )

    def _elapsed(self, start: float) -> float:
        if self.device == "cuda":
            self._torch.cuda.synchronize()  # GPU work is asynchronous: wait before reading the clock
        return time.perf_counter() - start


def parse_tool_calls(text: str) -> tuple[list[ToolCall], str]:
    """Split a Qwen reply into tool calls and the remaining plain text."""
    calls = []
    for n, block in enumerate(TOOL_CALL_RE.findall(text), start=1):
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        args = obj.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if isinstance(obj.get("name"), str):
            calls.append(ToolCall(id=f"call_{n}", name=obj["name"], arguments=args, raw_arguments=block))
    return calls, TOOL_CALL_RE.sub("", text).strip()


def _for_template(messages: list[dict]) -> list[dict]:
    """The Qwen template wants tool-call arguments as a dict, not a JSON string."""
    out = []
    for m in messages:
        if m.get("tool_calls"):
            m = {
                **m,
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": c["function"]["name"],
                            "arguments": json.loads(c["function"]["arguments"] or "{}"),
                        },
                    }
                    for c in m["tool_calls"]
                ],
            }
        out.append(m)
    return out
