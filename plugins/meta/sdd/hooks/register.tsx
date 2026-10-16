import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { SddAgent, SddChange, SddCheck } from '../types'
import {
  checkBash,
  checkPath,
  checkSdd,
  cleanCfg,
  frontStatus,
  relTo,
  roleOf,
  WRITE_TOOLS,
} from './guard'
import type { Cfg, Lookup, Role } from './guard'
import { infoOf, labelOf, phaseOf, phasesOf } from './phase'

type $ = EngineInterface

const PANE = 'sdd'
const PHASE_PANE = 'sdd-phase'
const TOOL = 'mcp__sdd__sdd'

const changes = atom({ plugin: 'sdd', key: 'changes' } as const, [])
const archived = atom({ plugin: 'sdd', key: 'archived' } as const, 0)
const rootDir = atom({ plugin: 'sdd', key: 'root' } as const, '')
const checks = atom({ plugin: 'sdd', key: 'checks' } as const, {})
const agents = atom({ plugin: 'sdd', key: 'agents' } as const, [])
const isBandHidden = atom({ plugin: 'sdd', key: 'isBandHidden' } as const, false)
const lastDeny = atom({ plugin: 'sdd', key: 'lastDeny' } as const, '')

const MUTATING = new Set(['init', 'new', 'set-status', 'delta-new', 'delta-stub', 'adr-new', 'adr-accept', 'freeze', 'sync', 'start', 'checkpoint', 'set-pr', 'resume', 'finish'])

const TOOL_DESCRIPTION = `Runs the spec-driven workflow tool (sdd.py) in the project. Pass the subcommand and its arguments as \`args\`, e.g. ["check", "add-login"].
Subcommands: init | config | status [<change>] | new <change> --title T | set-status <change> <draft|approved|implementing|verified|archived> | delta-new <change> <capability> | delta-stub <change> <REQ> [--remove] | adr-new <title> [--supersedes ADR-NNNN] | adr-accept <ADR> | check <change> [--tests] | context <change> <task> [--plan] | freeze <change> | verify-frozen <change> | sync <change> [--dry-run] [--force] | start <change> --title T [--pr-title P] [--base B] | checkpoint <change> [--phase P] [-m MSG] | set-pr <change> <number> [--url U] | resume <change> [--pr N] | finish <change>.
Lead-only: init, new, set-status, sync, adr-accept, start, checkpoint, set-pr, resume, finish. freeze: lead and acceptance-tester. delta-new, delta-stub, adr-new: lead and spec-author. Output is terse; ERROR lines name the file and the fix.`

// Appended to the main conversation's system prompt: makes it the workflow's lead.
const LEAD = `# sdd lead
You are the lead of the spec-driven (sdd) workflow in this repo. For any request to change the codebase (feature, behavior change, bug fix) or to \`resume <change-id>\` (also a change started elsewhere: it is fetched from its PR branch), invoke the \`sdd:change\` skill with the request verbatim as its argument and follow it. Questions, explanations and reviews need no workflow: answer them directly. If you are a subagent, ignore this section.`

// ---------------------------------------------------------------- helpers --

const agentTypes = new Map<string, string>()

async function roleFor($: $, agentId: string | undefined): Promise<Role> {
  if (agentId === undefined) return 'lead'
  let type = agentTypes.get(agentId)
  if (type === undefined) {
    const found = (await $.agent.list()).find(a => a.id === agentId)
    type = found?.type ?? ''
    if (found) agentTypes.set(agentId, type)
  }
  return roleOf(type)
}

async function readText($: $, path: string): Promise<string | undefined> {
  try {
    return await $.fs.read(path)
  } catch {
    return undefined
  }
}

async function loadCfg($: $, root: string): Promise<Cfg> {
  const text = await readText($, `${root}/.claude/sdd.json`)
  if (text === undefined) return cleanCfg(undefined)
  try {
    return cleanCfg(JSON.parse(text) as Partial<Cfg>)
  } catch {
    return cleanCfg(undefined)
  }
}

function lookupAt($: $, base: string, cfg: Cfg): Lookup {
  return {
    changeStatus: async ch => {
      const text = await readText($, `${base}/${cfg.changes_dir}/${ch}/intent.md`)
      return text === undefined ? undefined : frontStatus(text)
    },
    adrStatus: async rel => {
      const text = await readText($, `${base}/${rel}`)
      return text === undefined ? undefined : frontStatus(text)
    },
  }
}

async function runSdd($: $, args: string[], cwd: string) {
  return $.process.run(['python3', `${$.plugin.root}/tools/sdd.py`, ...args], { cwd, timeoutMs: 120_000 })
}

async function refreshChanges($: $) {
  // the cwd: after EnterWorktree it is the change's worktree, whose changes/ is the live one
  const cwd = await $.session.cwd()
  let parsed: { root: string; changes: SddChange[]; archived: number }
  try {
    const out = await runSdd($, ['status', '--json'], cwd)
    if (out.exitCode !== 0) return
    parsed = JSON.parse(out.stdout) as typeof parsed
  } catch {
    return
  }
  const before = JSON.stringify(await read($, changes))
  if (before !== JSON.stringify(parsed.changes)) await update($, changes, () => parsed.changes)
  if ((await read($, archived)) !== parsed.archived) await update($, archived, () => parsed.archived)
  if ((await read($, rootDir)) !== parsed.root) await update($, rootDir, () => parsed.root)
}

async function refreshAgents($: $) {
  const live: SddAgent[] = (await $.agent.list())
    .filter(a => a.type.startsWith('sdd:') && (a.status === 'running' || a.status === 'pending' || a.status === 'waiting'))
    .map(a => ({ id: a.id, type: a.type.slice(4), description: a.description, status: a.status }))
  if (JSON.stringify(await read($, agents)) !== JSON.stringify(live)) await update($, agents, () => live)
}

async function recordCheck($: $, change: string, withTests: boolean, stdout: string, at: number) {
  const lines = stdout.split('\n').filter(l => l.startsWith('ERROR') || l.startsWith('WARN'))
  const summary = stdout.split('\n').find(l => /^(OK|FAIL) /.test(l)) ?? stdout.trim().split('\n').pop() ?? ''
  const check: SddCheck = { isOk: summary.startsWith('OK'), summary, lines: lines.slice(0, 12), at, withTests }
  await update($, checks, all => ({ ...(all ?? {}), [change]: check }))
}

const isOpen = (c: SddChange) => c.status !== 'archived'
const doneOf = (c: SddChange) => c.tasks.filter(t => t.done).length
const RANK: Record<string, number> = { implementing: 0, verified: 1, approved: 2, draft: 3 }
const byActivity = (a: SddChange, b: SddChange) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9)

// ------------------------------------------------------------------ hooks --

export const register: Register = on => {
  on('prompt.compose', async ($, e, next) => {
    const { sections } = await next(e)
    return { sections: [...sections, { id: 'sdd:lead', text: LEAD, scope: 'session' }] }
  })

  on('session.start', async ($, e, next) => {
    await $.tool.register({
      name: 'sdd',
      description: TOOL_DESCRIPTION,
      inputSchema: {
        type: 'object',
        properties: {
          args: {
            type: 'array',
            items: { type: 'string' },
            description: 'Subcommand then its arguments, e.g. ["context", "add-login", "T2", "--plan"]',
          },
        },
        required: ['args'],
      },
      isDeferred: false,
    })
    await $.command.register({
      name: 'sdd',
      description: 'Spec-driven workflow: open the status pane (`/sdd phase` for the phase pane, `/sdd refresh`)',
      argumentHint: '[phase|refresh]',
    })
    void refreshChanges($)
    $.clock.every(4_000, () => void refreshAgents($))
    $.clock.every(30_000, () => void refreshChanges($))

    return next(e)
  })

  on('command.run', { command: 'sdd' }, async ($, e) => {
    await refreshChanges($)
    const arg = e.args.trim()
    if (arg === 'refresh') return { text: 'sdd: status refreshed.' }
    if (arg === 'phase') {
      await $.ui.open({ id: PHASE_PANE, title: 'sdd phase' })
      return { text: 'sdd: phase pane opened.' }
    }
    await update($, isBandHidden, () => false)
    await $.ui.open({ id: PANE, title: 'Spec-driven workflow' })
    return { text: 'sdd: status pane opened.' }
  })

  // The tool every agent uses instead of a script path.
  on('tool.call', { tool: TOOL }, async ($, e) => {
    const raw = (e as unknown as { args?: unknown }).args
    const args = Array.isArray(raw) ? raw.map(String) : []
    const role = await roleFor($, e.agentId)
    const refusal = checkSdd(args[0], role)
    if (refusal !== undefined) return { deny: `[sdd] ${refusal}` }

    const cwd = await $.session.cwd()
    let out
    try {
      out = await runSdd($, args, cwd)
    } catch (err) {
      return { deny: `[sdd] could not run python3 (${String(err)}). Python 3.9+ must be on PATH.` }
    }
    const text = [out.stdout.trimEnd(), out.stderr.trim() && `stderr: ${out.stderr.trim()}`]
      .filter(Boolean)
      .join('\n')
    if (args[0] === 'check' && args[1]) {
      await recordCheck($, args[1], args.includes('--tests'), out.stdout, await $.clock.now())
    }
    if (MUTATING.has(args[0] ?? '') || args[0] === 'check') void refreshChanges($)

    return { result: `${text || '(no output)'}${out.exitCode === 0 ? '' : `\n(exit ${out.exitCode})`}` }
  }).catch(() => ({ deny: '[sdd] the sdd tool failed unexpectedly; retry once, then tell the lead.' }))

  // The guard: who may write what, decided from the calling agent.
  on('tool.call', async ($, e, next) => {
    const tool = String(e.tool)
    if (!WRITE_TOOLS.has(tool) && tool !== 'Bash') return next(e)

    const role = await roleFor($, e.agentId)
    if (tool === 'Bash' && role === 'lead') return next(e)
    // the root sdd.py resolved (where specs/ and .claude/sdd.json live), else the session's
    const root = (await read($, rootDir)) || (await $.session.root())
    const cwd = await $.session.cwd()
    const bases = cwd === root ? [root] : [cwd, root]
    const cfg = await loadCfg($, root)
    const input = e as unknown as {
      file_path?: string
      notebook_path?: string
      command?: string
      content?: string
      new_string?: string
      new_source?: string
      edits?: { new_string?: string }[]
    }
    const written = [input.content, input.new_string, input.new_source, ...(input.edits ?? []).map(x => x.new_string)]
      .filter((s): s is string => typeof s === 'string')
      .join('\n')

    let reason: string | undefined
    let touchesChanges = false
    if (tool === 'Bash') {
      reason = checkBash(input.command ?? '', role, cfg, bases)
    } else {
      const path = input.file_path ?? input.notebook_path
      if (path !== undefined) {
        const hit = relTo(path, bases)
        if (hit === undefined) {
          reason = role === 'lead' ? undefined : `${path} is outside the project.`
        } else {
          reason = await checkPath(hit.rel, role, cfg, lookupAt($, hit.base, cfg), written)
          touchesChanges = hit.rel.startsWith(`${cfg.changes_dir}/`)
        }
      }
    }

    if (reason !== undefined) {
      const who = role === 'lead' ? 'lead' : role
      $.ui.toast(`sdd guard (${who}): ${reason.slice(0, 120)}`)
      await update($, lastDeny, () => `${who}: ${reason}`)
      return { deny: `[sdd-guard] ${reason}` }
    }

    const ran = await next(e)
    if (touchesChanges) void refreshChanges($)
    return ran
  }).catch(($, e, next) =>
    next.called ? next(e) : e.agentId !== undefined ? { deny: '[sdd-guard] the guard failed; refusing for safety.' } : next(e),
  )

  // A workflow agent starting or finishing shows at once, not on the next tick.
  on('agent.spawn', async ($, e, next) => {
    const spawned = await next(e)
    void refreshAgents($)
    return spawned
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    void refreshAgents($)
    return next(e)
  })

  // ----------------------------------------------------------------- drawing --

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey || (await read($, isBandHidden))) return next(e)
    const open = ((await read($, changes)) ?? []).filter(isOpen).sort(byActivity)
    const top = open[0]
    if (top === undefined) return next(e)

    const { Box, Button, Text } = $.ui.resolve(e)
    const check = ((await read($, checks)) ?? {})[top.id]
    const running = ((await read($, agents)) ?? []).map(a => a.type)

    return (
      <Box flexDirection="row" gap={1}>
        <Text bold>sdd</Text>
        <Text>{top.id}</Text>
        <Text dimColor>
          {labelOf(phaseOf(top, running))} · {top.status} · {doneOf(top)}/{top.tasks.length} tasks
          {top.pr ? ` · PR #${top.pr}` : ''}
          {check ? ` · check ${check.isOk ? 'ok' : 'fail'}` : ''}
          {running.length > 0 ? ` · ${running.join(', ')} running` : ''}
          {open.length > 1 ? ` · +${open.length - 1} open` : ''}
        </Text>
        <Button key="open" label="Open" onPress={() => $.ui.open({ id: PANE, title: 'Spec-driven workflow' })} />
        <Button key="hide" label="Hide" onPress={() => update($, isBandHidden, () => true)} />
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const all = ((await read($, changes)) ?? []).filter(isOpen).sort(byActivity)
    const results = (await read($, checks)) ?? {}
    const running = (await read($, agents)) ?? []
    const nArchived = (await read($, archived)) ?? 0
    const denied = (await read($, lastDeny)) ?? ''
    const types = running.map(a => a.type)

    const runCheck = async (id: string, withTests: boolean) => {
      const cwd = await $.session.cwd()
      const args = withTests ? ['check', id, '--tests'] : ['check', id]
      const out = await runSdd($, args, cwd)
      await recordCheck($, id, withTests, out.stdout, await $.clock.now())
    }

    return (
      <Box flexDirection="column" gap={1}>
        {all.length === 0 && (
          <Text dimColor>No open change. Start one with /sdd:change &lt;what you want&gt;.</Text>
        )}
        {all.map(c => {
          const check = results[c.id]
          const phase = infoOf(phaseOf(c, types))
          return (
            <Box key={`c-${c.id}`} flexDirection="column">
              <Box flexDirection="row" gap={1}>
                <Text bold>{c.id}</Text>
                <Text color={c.status === 'verified' ? 'green' : undefined}>{c.status}</Text>
                <Text dimColor>
                  {doneOf(c)}/{c.tasks.length} tasks{c.adrs.length > 0 ? ` · ${c.adrs.join(', ')}` : ''}
                  {c.pr ? ` · PR #${c.pr}` : ''}
                </Text>
              </Box>
              {phase && (
                <Text dimColor>
                  {phase.label}: {phase.hint}
                </Text>
              )}
              {c.tasks.map(t => (
                <Text key={`t-${c.id}-${t.id}`} dimColor={t.done}>
                  {t.done ? '[x]' : '[ ]'} {t.id} {t.kind} {t.reqs.join(' ')}
                </Text>
              ))}
              {check && (
                <Text color={check.isOk ? 'green' : 'red'}>
                  {check.withTests ? 'check --tests: ' : 'check: '}
                  {check.summary}
                </Text>
              )}
              {check?.lines.map((l, i) => (
                <Text key={`l-${c.id}-${i}`} dimColor>
                  {l}
                </Text>
              ))}
              <Box flexDirection="row" gap={1}>
                <Button key={`check-${c.id}`} label="Check" onPress={() => runCheck(c.id, false)} />
                <Button key={`tests-${c.id}`} label="Check + tests" onPress={() => runCheck(c.id, true)} />
              </Box>
            </Box>
          )
        })}
        <Box flexDirection="column">
          <Text bold>Workflow agents</Text>
          {running.length === 0 ? (
            <Text dimColor>none running</Text>
          ) : (
            running.map(a => (
              <Text key={`a-${a.id}`}>
                {a.type} <Text dimColor>{a.description}</Text>
              </Text>
            ))
          )}
        </Box>
        {denied !== '' && <Text dimColor>last guard refusal: {denied}</Text>}
        <Box flexDirection="row" gap={1}>
          <Text dimColor>{nArchived} archived</Text>
          <Button key="refresh" label="Refresh" onPress={() => refreshChanges($)} />
        </Box>
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PHASE_PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const open = ((await read($, changes)) ?? []).filter(isOpen).sort(byActivity)
    const running = ((await read($, agents)) ?? []).map(a => a.type)
    const top = open[0]
    if (top === undefined) {
      return <Text dimColor>No open change: triage. Describe a change or run /sdd:change.</Text>
    }

    const steps = phasesOf(top)
    const current = phaseOf(top, running)
    const at = steps.findIndex(p => p.id === current)

    return (
      <Box flexDirection="column" gap={1}>
        <Box flexDirection="row" gap={1}>
          <Text bold>{top.id}</Text>
          <Text dimColor>
            {top.status} · {doneOf(top)}/{top.tasks.length} tasks
            {running.length > 0 ? ` · ${running.join(', ')} running` : ''}
          </Text>
        </Box>
        <Box flexDirection="column">
          {steps.map((p, i) => (
            <Text
              key={`p-${p.id}`}
              bold={i === at}
              color={i === at ? 'cyan' : i < at ? 'green' : undefined}
              dimColor={i > at}
            >
              {i === at ? '▶' : i < at ? '✓' : '·'} {i + 1}. {p.label}
              {i === at ? ` — ${p.hint}` : ''}
            </Text>
          ))}
        </Box>
        {at === -1 && <Text dimColor>No workflow phase for status {top.status}.</Text>}
        {open.slice(1).map(c => (
          <Text key={`o-${c.id}`} dimColor>
            also open: {c.id} · {labelOf(phaseOf(c, running))}
          </Text>
        ))}
      </Box>
    )
  })
}
