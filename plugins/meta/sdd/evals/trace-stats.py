#!/usr/bin/env python3
"""Summarise a kept eval run's trace: who did what, and who spent the tokens.

    python3 trace-stats.py <run dir>/out/trace.jsonl [...]

Run the eval with `--keep-temp` to keep the trace. Per trace it prints the lead's turns,
spawns per agent type, SendMessage resumes, `sleep` polls, the lead's `sdd` calls by
subcommand, and each agent's share of a weighted token count: input + cache creation +
cache reads / 10 + output * 5 (a cost proxy that ignores the model each agent runs on).
"""
from __future__ import annotations

import collections
import json
import re
import sys

AGENT_TOOLS = ("Agent", "Task")
SLEEP_RE = re.compile(r"(?:^|[;&|(]\s*)sleep\s")  # a `sleep N` command, not a word in a path or grep
USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def stats(path: str) -> dict:
    owner: dict[str, str] = {}          # Agent/SendMessage tool_use id -> who answers under it
    usage: dict[str, tuple[str, dict]] = {}  # assistant message id -> (who, largest usage seen)
    spawns: collections.Counter = collections.Counter()
    sdd: collections.Counter = collections.Counter()
    sends = sleeps = 0
    with open(path) as f:
        for n, line in enumerate(f):
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("type") != "assistant":
                continue
            m = e.get("message") or {}
            parent = e.get("parent_tool_use_id")
            content = m.get("content") if isinstance(m.get("content"), list) else []
            for c in content:
                if c.get("type") != "tool_use":
                    continue
                name, inp = c["name"], c.get("input") or {}
                if name in AGENT_TOOLS:
                    owner[c["id"]] = inp.get("subagent_type") or "general-purpose"
                elif name == "SendMessage":  # a resumed agent may answer under this id
                    owner[c["id"]] = f"resumed {inp.get('to', '?')}"
                if parent:
                    continue
                if name in AGENT_TOOLS:
                    spawns[owner[c["id"]]] += 1
                elif name == "SendMessage":
                    sends += 1
                elif name == "Bash" and SLEEP_RE.search(inp.get("command") or ""):
                    sleeps += 1
                elif name == "mcp__sdd__sdd" and inp.get("args"):
                    sdd[inp["args"][0]] += 1
            # a streamed message arrives as one event per content block, all with its id; its
            # output count may grow from event to event, so keep the largest of each field
            mid = m.get("id") or f"line {n}"
            who = owner.get(parent, "?") if parent else "lead"
            u = m.get("usage") or {}
            prev = usage.get(mid, (who, {}))[1]
            usage[mid] = (who, {k: max(prev.get(k) or 0, u.get(k) or 0) for k in USAGE_KEYS})
    tokens: collections.Counter = collections.Counter()
    for who, u in usage.values():
        tokens[who] += (u["input_tokens"] + u["cache_creation_input_tokens"]
                        + u["cache_read_input_tokens"] // 10 + 5 * u["output_tokens"])
    lead_turns = sum(who == "lead" for who, _ in usage.values())
    return {"lead_turns": lead_turns, "spawns": spawns, "sends": sends, "sleeps": sleeps,
            "sdd": sdd, "tokens": tokens}


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__.strip())
        return 2
    for path in paths:
        s = stats(path)
        total = sum(s["tokens"].values()) or 1
        print(f"== {path}")
        print(f"lead turns {s['lead_turns']}   resumes (SendMessage) {s['sends']}   sleep polls {s['sleeps']}")
        print("spawns     " + ", ".join(f"{k} {v}" for k, v in s["spawns"].most_common()))
        print("lead sdd   " + ", ".join(f"{k} {v}" for k, v in s["sdd"].most_common()))
        print(f"weighted tokens {total}")
        for who, n in s["tokens"].most_common():
            print(f"  {who:24s} {n:>9d}  {100 * n / total:5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
