import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { SddAgent, SddChange, SddCheck } from '../types'
import {
  checkBash,
  checkBundle,
  checkPath,
  checkSdd,
  cleanCfg,
  frontStatus,
  relTo,
  roleOf,
  WRITE_TOOLS,
} from './guard'
import type { Cfg, Lookup, Role } from './guard'
import { activeOf, byActivity, byStatus, infoOf, labelOf, phaseOf, phasesOf, stepOf } from './phase'

type $ = EngineInterface

const PANE = 'sdd'
const PHASE_PANE = 'sdd-phase'
const TOOL = 'mcp__sdd__sdd'
const BUNDLE_TOOL = 'mcp__sdd__bundle'

const changes = atom({ plugin: 'sdd', key: 'changes' } as const, [])
const archived = atom({ plugin: 'sdd', key: 'archived' } as const, 0)
const rootDir = atom({ plugin: 'sdd', key: 'root' } as const, '')
const checks = atom({ plugin: 'sdd', key: 'checks' } as const, {})
const agents = atom({ plugin: 'sdd', key: 'agents' } as const, [])
const isBandHidden = atom({ plugin: 'sdd', key: 'isBandHidden' } as const, false)
const lastDeny = atom({ plugin: 'sdd', key: 'lastDeny' } as const, '')
const branch = atom({ plugin: 'sdd', key: 'branch' } as const, '')
const expanded = atom({ plugin: 'sdd', key: 'expanded' } as const, [])

const MUTATING = new Set(['init', 'new', 'set-status', 'delta-new', 'delta-stub', 'adr-new', 'adr-accept', 'freeze', 'sync', 'start', 'checkpoint', 'set-pr', 'requires', 'resume', 'finish', 'bundle'])

const TOOL_DESCRIPTION = `Runs the spec-driven workflow tool (sdd.py) in the project. Pass the subcommand and its arguments as \`args\`, e.g. ["check", "add-login"].
Subcommands: init [--survey] [key=value ...] | config | status [<change>] | new <change> --title T | set-status <change> <draft|approved|implementing|verified|archived> | delta-new <change> <capabilities/<id>|invariants/<id>> [--title T] | delta-stub <change> <capabilities/<id>#AC-NN [--retire] | capabilities/<id> --section <Title|Description|Intent|Scope|Invariants|Decisions|Verification> | capabilities/<id> --deprecate | invariants/<id> [--deprecate]> | adr-new <title> [--supersedes ADR-NNNN] | adr-accept <ADR> | check <change> [--tests] | context <change> <task> [--plan] | freeze <change> | verify-frozen <change> | sync <change> [--dry-run] [--force] | bundle <specs|adrs|change> [--fix] | start <change> --title T [--pr-title P] [--base B] [--requires a,b] | requires <change> [<dep>... | --clear] | deps <change> | checkpoint <change> [--phase P] [-m MSG] | set-pr <change> <number> [--url U] | resume <change> [--pr N] | finish <change>.
Lead-only: init, new, set-status, sync, adr-accept, start, checkpoint, set-pr, requires, resume, finish. deps is read-only. freeze: lead and acceptance-tester. delta-new, delta-stub, adr-new: lead and spec-author. Output is terse; ERROR lines name the file and the fix. Bundle validation and repair of specs/, adrs/ and changes/<id>/ is the separate \`bundle\` tool (also reachable as \`sdd bundle <specs|adrs|change> [--fix]\`, with the same role rules).`

const BUNDLE_DESCRIPTION = `Checks an OKF bundle of the spec-driven workflow and, with \`fix\`, repairs it. \`target\` is "specs" (the living specs/capabilities/ and specs/invariants/ concepts, their indexes and log), "adrs" (adrs/NNNN_<slug>.md, index, log) or a change id (changes/<id>/: intent, plan, tasks, the new concepts and CapabilityDeltas under specs/, indexes). Checks: layout, snake_case concept ids, Capability/Invariant/ADR structure and front matter, AC order, indexes as \`okf index\` writes them, log date groups, missing sources, the old REQ/INV format (reported, never migrated). Output: FIXED/WARN/ERROR lines, then OK or FAIL. \`fix\` repairs what is marked [fixable] and is idempotent. Check is open to every role; fix on "specs" or "adrs" is lead-only, fix on a change is lead or spec-author.`

// Appended to the main conversation's system prompt: makes it the workflow's lead.
const LEAD = `# sdd lead
You are the lead of the spec-driven (sdd) workflow in this repo. For any request to change the codebase (feature, behavior change, bug fix), to \`resume <change-id>\` (also a change started elsewhere: it is fetched from its PR branch), or to \`adopt <area>\` (write down what existing code does as a spec), invoke the \`sdd:change\` skill with the request verbatim as its argument and follow it. Questions, explanations and reviews need no workflow: answer them directly. If you are a subagent, ignore this section.`

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
  // the branch checked out here names the change being worked on (`sdd start` makes sdd/<id>)
  let current = ''
  try {
    const out = await $.process.run(['git', 'branch', '--show-current'], { cwd, timeoutMs: 10_000 })
    if (out.exitCode === 0) current = out.stdout.trim()
  } catch {
    // not a git checkout: fall back to the most active change
  }
  if ((await read($, branch)) !== current) await update($, branch, () => current)
}

// The open changes, most active first, and the one being worked on.
async function openChanges($: $) {
  const all = byActivity(((await read($, changes)) ?? []).filter(isOpen))
  return { all, top: activeOf(all, (await read($, branch)) ?? '') }
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

const BAR = 12
const barOf = (done: number, total: number) => {
  // floor: the bar fills only when every task is done
  const full = total === 0 ? 0 : Math.floor((done / total) * BAR)
  return '█'.repeat(full) + '░'.repeat(BAR - full)
}
const tasksOf = (c: SddChange) => (c.tasks.length === 0 ? 'no tasks yet' : `${doneOf(c)}/${c.tasks.length} tasks`)

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
    await $.tool.register({
      name: 'bundle',
      description: BUNDLE_DESCRIPTION,
      inputSchema: {
        type: 'object',
        properties: {
          target: { type: 'string', description: '"specs", "adrs" or a change id, e.g. "add-login"' },
          fix: { type: 'boolean', description: 'repair the fixable findings (default: only report)' },
        },
        required: ['target'],
      },
      isDeferred: false,
    })
    await $.command.register({
      name: 'sdd',
      description:
        'Spec-driven workflow: open the status pane (`/sdd phase` for the phase pane, `/sdd refresh`, `/sdd check <change> [--tests]`)',
      argumentHint: '[phase|refresh|check <change> [--tests]]',
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
    const [verb, id, ...flags] = arg.split(/\s+/)
    if (verb === 'check') {
      if (!id) return { text: 'sdd: usage: /sdd check <change> [--tests]' }
      const withTests = flags.includes('--tests')
      const out = await runSdd($, withTests ? ['check', id, '--tests'] : ['check', id], await $.session.cwd())
      await recordCheck($, id, withTests, out.stdout, await $.clock.now())
      return { text: out.stdout.trimEnd() || out.stderr.trim() || `(exit ${out.exitCode})` }
    }
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
    // the target is the one positional argument, wherever `--fix` sits (sdd.py strips it from any position)
    const bundleTarget = args.slice(1).filter(a => a !== '--fix')
    const refusal =
      args[0] === 'bundle'
        ? bundleTarget.length === 1
          ? checkBundle(bundleTarget[0], args.includes('--fix'), role)
          : 'usage: bundle <specs|adrs|change> [--fix]'
        : checkSdd(args[0], role)
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

  // The bundle checker: sdd.py's `bundle` subcommand, with its own role rule.
  on('tool.call', { tool: BUNDLE_TOOL }, async ($, e) => {
    const raw = e as unknown as { target?: unknown; fix?: unknown }
    const target = typeof raw.target === 'string' ? raw.target : undefined
    const fix = raw.fix === true
    const refusal = checkBundle(target, fix, await roleFor($, e.agentId))
    if (refusal !== undefined) return { deny: `[sdd] ${refusal}` }

    let out
    try {
      out = await runSdd($, ['bundle', target as string, ...(fix ? ['--fix'] : [])], await $.session.cwd())
    } catch (err) {
      return { deny: `[sdd] could not run python3 (${String(err)}). Python 3.9+ must be on PATH.` }
    }
    if (fix) void refreshChanges($)
    const text = [out.stdout.trimEnd(), out.stderr.trim() && `stderr: ${out.stderr.trim()}`].filter(Boolean).join('\n')
    return { result: `${text || '(no output)'}${out.exitCode === 0 ? '' : `\n(exit ${out.exitCode})`}` }
  }).catch(() => ({ deny: '[sdd] the bundle tool failed unexpectedly; retry once, then tell the lead.' }))

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
    const { all: open, top } = await openChanges($)
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
    const { all, top } = await openChanges($)
    const results = (await read($, checks)) ?? {}
    const running = (await read($, agents)) ?? []
    const nArchived = (await read($, archived)) ?? 0
    const denied = (await read($, lastDeny)) ?? ''
    const unfolded = (await read($, expanded)) ?? []
    const types = running.map(a => a.type)

    // The change being worked on in full; the others in status groups, folded until opened.
    const phase = top && infoOf(phaseOf(top, types))
    const check = top && results[top.id]
    const groups = byStatus(all.filter(c => c !== top))
    const checkLines = (id: string, lines: string[]) =>
      lines.map((l, i) => (
        <Text key={`l-${id}-${i}`} dimColor>
          {'    '}
          {l}
        </Text>
      ))
    const toggle = (status: string) =>
      update($, expanded, open => (open.includes(status) ? open.filter(s => s !== status) : [...open, status]))

    return (
      <Box flexDirection="column" gap={1}>
        <Text dimColor>
          {all.length} open · {running.length === 0 ? 'no agent running' : `${running.length} running`} · {nArchived} archived
        </Text>

        {top === undefined && <Text dimColor>No open change. Start one with /sdd:change &lt;what you want&gt;.</Text>}

        {top && (
          <Box flexDirection="column">
            <Text>
              <Text bold color="cyan">▶ {top.id}</Text>
              <Text dimColor>
                {' '}
                {top.status}
                {top.pr ? ` · PR #${top.pr}` : ''}
                {top.branch ? ` · ${top.branch}` : ''}
              </Text>
            </Text>
            {top.title !== top.id && <Text>{'  '}{top.title}</Text>}
            {phase && (
              <Text>
                {'  '}
                <Text bold>{phase.label}</Text>
                <Text dimColor> — {phase.hint}</Text>
              </Text>
            )}
            {top.tasks.length > 0 && (
              <Text>
                {'  '}
                <Text color="green">{barOf(doneOf(top), top.tasks.length)}</Text> {tasksOf(top)}
              </Text>
            )}
            {top.tasks.map(t => (
              <Text key={`t-${t.id}`} dimColor={t.done}>
                {'    '}
                {t.done ? '[x]' : '[ ]'} {t.id} {t.kind} <Text dimColor>{t.refs.join(' ')}</Text>
              </Text>
            ))}
            {top.adrs.length > 0 && <Text dimColor>{'  '}ADRs: {top.adrs.join(', ')}</Text>}
            {top.requires && top.requires.length > 0 && <Text color="yellow">{'  '}requires: {top.requires.join(', ')}</Text>}
            {check && (
              <Text color={check.isOk ? 'green' : 'red'}>
                {'  '}last {check.withTests ? 'check --tests' : 'check'}: {check.summary}
              </Text>
            )}
            {check && checkLines(top.id, check.lines)}
          </Box>
        )}

        {groups.length > 0 && (
          <Box flexDirection="column">
            {groups.map(([status, cs], i) => {
              const isOpenGroup = unfolded.includes(status)
              const failed = cs.filter(c => results[c.id]?.isOk === false).length
              return (
                <Box key={`g-${status}`} flexDirection="column">
                  <Button
                    key={`fold-${status}`}
                    plain
                    hotkey={i < 9 ? String(i + 1) : undefined}
                    onPress={() => toggle(status)}
                  >
                    {isOpenGroup ? '▾' : '▸'} {status} ({cs.length})
                    <Text dimColor>{isOpenGroup ? '' : ` ${cs.map(c => c.id).join(', ')}`}</Text>
                    {failed > 0 && <Text color="red"> · {failed} check failed</Text>}
                  </Button>
                  {isOpenGroup &&
                    cs.map(c => {
                      const r = results[c.id]
                      return (
                        <Box key={`c-${c.id}`} flexDirection="column">
                          <Text>
                            {'    '}
                            {c.id}
                            <Text dimColor>
                              {' '}
                              {labelOf(phaseOf(c, []))} · {tasksOf(c)}
                              {c.pr ? ` · PR #${c.pr}` : ''}
                            </Text>
                            {c.requires && c.requires.length > 0 && <Text color="yellow"> · requires {c.requires.join(', ')}</Text>}
                            {r && <Text color={r.isOk ? 'green' : 'red'}> · check {r.isOk ? 'ok' : 'fail'}</Text>}
                          </Text>
                          {r && !r.isOk && checkLines(c.id, r.lines)}
                        </Box>
                      )
                    })}
                </Box>
              )
            })}
          </Box>
        )}

        {running.length > 0 && (
          <Box flexDirection="column">
            <Text bold>Running</Text>
            {running.map(a => (
              <Text key={`a-${a.id}`}>
                {'  '}
                {a.type} <Text dimColor>{a.description}</Text>
              </Text>
            ))}
          </Box>
        )}
        {denied !== '' && <Text color="yellow">last guard refusal: {denied}</Text>}
        <Text dimColor>/sdd check &lt;change&gt; [--tests] · /sdd refresh · /sdd phase</Text>
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PHASE_PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const { all: open, top } = await openChanges($)
    const running = ((await read($, agents)) ?? []).map(a => a.type)
    if (top === undefined) {
      return <Text dimColor>No open change: triage. Describe a change or run /sdd:change.</Text>
    }

    const steps = phasesOf(top)
    const at = stepOf(top, running)

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
        {open.filter(c => c !== top).map(c => (
          <Text key={`o-${c.id}`} dimColor>
            also open: {c.id} · {labelOf(phaseOf(c, running))}
          </Text>
        ))}
      </Box>
    )
  })
}
