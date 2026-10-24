import type { SddChange } from '../types'

// The workflow phases of skills/change, in order. Triage happens before a change exists.
export const PHASES = [
  { id: 'spec', label: 'Spec', hint: 'spec-author writes intent, delta and ADRs' },
  { id: 'gate1', label: 'Gate 1', hint: 'your review: intent, capabilities, invariants and ADRs' },
  { id: 'plan', label: 'Plan', hint: 'planner writes plan.md and tasks.md' },
  { id: 'gate2', label: 'Gate 2', hint: 'sdd check, then set implementing' },
  { id: 'acceptance', label: 'Acceptance tests', hint: 'acceptance-tester writes failing tests, then freeze' },
  { id: 'implement', label: 'Implement', hint: 'implementers make the frozen tests pass' },
  { id: 'verify', label: 'Verify', hint: 'verifier runs the suites and reviews the diff, then code-review' },
  { id: 'sync', label: 'Sync', hint: 'sdd sync merges the delta into specs/ and archives' },
] as const

export type PhaseId = (typeof PHASES)[number]['id']

// A fix has no spec delta and its contract is the existing code: its acceptance tests are
// written alongside the plan, before Gate 2.
const FIX_ORDER: readonly PhaseId[] = ['plan', 'acceptance', 'gate2', 'implement', 'verify', 'sync']

// A baseline (adopt) only writes down behavior the code already has: its tests must pass on
// the current code, so nothing is implemented.
const BASELINE_ORDER: readonly PhaseId[] = ['spec', 'gate1', 'plan', 'gate2', 'acceptance', 'verify', 'sync']

export function phasesOf(change: SddChange) {
  const order = change.size === 'fix' ? FIX_ORDER : change.size === 'baseline' ? BASELINE_ORDER : undefined
  if (!order) return [...PHASES]
  return order.map(id => PHASES.find(p => p.id === id)!)
}

// The phase `sdd checkpoint` stored in the change's state.json wins: it survives a restart
// and a resume on another machine. Without one (older changes) it is derived from the
// change's status, its tasks and the workflow agents running (types without the `sdd:`
// prefix). Agents are session-wide, so they only refine within a status.
export function phaseOf(change: SddChange, running: readonly string[]): PhaseId | undefined {
  // only a phase this kind of change has (a fix lists no spec or Gate 1)
  if (phasesOf(change).some(p => p.id === change.phase)) return change.phase as PhaseId
  const isRunning = (type: string) => running.includes(type)
  const open = (kind: string) => change.tasks.some(t => t.kind === kind && !t.done)
  switch (change.status) {
    case 'draft':
      // A fix starts with the lead's test task; planner and acceptance-tester run together,
      // and it goes from draft to implementing at Gate 2 once both are done.
      if (change.size === 'fix') {
        if (isRunning('planner') || !change.tasks.some(t => t.kind === 'impl')) return 'plan'
        return isRunning('acceptance-tester') || open('test') ? 'acceptance' : 'gate2'
      }
      return isRunning('spec-author') ? 'spec' : 'gate1'
    case 'approved':
      return isRunning('planner') || change.tasks.length === 0 ? 'plan' : 'gate2'
    case 'implementing':
      if (isRunning('acceptance-tester') || open('test')) return 'acceptance'
      if (isRunning('implementer') || open('impl') || open('chore')) return 'implement'
      return 'verify'
    case 'verified':
      return 'sync'
    default:
      return undefined
  }
}

export function infoOf(id: PhaseId | undefined) {
  return PHASES.find(p => p.id === id)
}

export function labelOf(id: PhaseId | undefined): string {
  return infoOf(id)?.label ?? 'unknown'
}

// The position of a change's phase in its own workflow (a fix's order differs), -1 without one.
export function stepOf(change: SddChange, running: readonly string[] = []): number {
  const id = phaseOf(change, running)
  return phasesOf(change).findIndex(p => p.id === id)
}

const RANK: Record<string, number> = { implementing: 0, verified: 1, approved: 2, draft: 3 }

// Most active first: by status, then furthest in its own workflow, then most tasks (a planned
// change before an unplanned one). Running agents are session-wide and name no change, so the
// ranking ignores them.
export function byActivity(changes: readonly SddChange[]): SddChange[] {
  return changes
    .map(c => ({ c, rank: RANK[c.status] ?? 9, step: stepOf(c), n: c.tasks.length }))
    .sort((a, b) => a.rank - b.rank || b.step - a.step || b.n - a.n)
    .map(x => x.c)
}

// The order of the status groups: the work in progress first.
export const STATUS_ORDER = ['implementing', 'verified', 'approved', 'draft'] as const

// Changes grouped by status in STATUS_ORDER, unknown statuses last; each group keeps the input's order.
export function byStatus(changes: readonly SddChange[]): [string, SddChange[]][] {
  const groups = new Map<string, SddChange[]>()
  for (const c of changes) {
    const group = groups.get(c.status)
    if (group) group.push(c)
    else groups.set(c.status, [c])
  }
  const at = (s: string) => {
    const i = (STATUS_ORDER as readonly string[]).indexOf(s)
    return i === -1 ? STATUS_ORDER.length : i
  }
  return [...groups].sort(([a], [b]) => at(a) - at(b))
}

// The change being worked on: the one whose branch is checked out in the session's cwd,
// else the most active. `changes` is already in byActivity order.
export function activeOf(changes: readonly SddChange[], branch: string): SddChange | undefined {
  return (branch !== '' && changes.find(c => c.branch === branch)) || changes[0]
}
