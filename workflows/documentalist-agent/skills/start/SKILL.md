---
name: start
description: Start the documentalist agent in the background so other agents can ask it codebase questions. Use when the user says "start the documentalist", "launch documentalist", or "/documentalist-agent:start".
---

Start the documentalist as a named background agent.

1. Call `ListAgents`. If an agent named `documentalist` already exists, report that it is running and stop. Do not start a second one.
2. Call `Agent` with:
   - `subagent_type`: `documentalist-agent:documentalist`
   - `name`: `documentalist`
   - `description`: `Codebase documentalist`
   - `prompt`: `Run your On start steps, then report the bundle status in one line and wait for questions.`
3. Tell the user how to query it: `SendMessage({to: "documentalist", message: "<question>"})`.
