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
import sys

AGENT_TOOLS = ("Agent", "Task")


def stats(path: str) -> dict:
    owner: dict[str, str] = {}          # Agent tool_use id -> subagent type
    seen: set[str] = set()              # assistant message ids already counted
    tokens: collections.Counter = collections.Counter()
    spawns: collections.Counter = collections.Counter()
    sdd: collections.Counter = collections.Counter()
    lead_turns = sends = sleeps = 0
    with open(path) as f:
        for line in f:
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
                if parent:
                    continue
                if name in AGENT_TOOLS:
                    spawns[owner[c["id"]]] += 1
                elif name == "SendMessage":
                    sends += 1
                elif name == "Bash" and "sleep" in inp.get("command", ""):
                    sleeps += 1
                elif name == "mcp__sdd__sdd" and inp.get("args"):
                    sdd[inp["args"][0]] += 1
            mid = m.get("id")
            if mid in seen:  # a streamed message arrives as one event per content block
                continue
            seen.add(mid)
            who = owner.get(parent, "?") if parent else "lead"
            lead_turns += who == "lead"
            u = m.get("usage") or {}
            tokens[who] += (u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                            + u.get("cache_read_input_tokens", 0) // 10 + 5 * u.get("output_tokens", 0))
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
