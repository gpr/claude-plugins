import type { SddChange } from '../types'

// The workflow phases of skills/change, in order. Triage happens before a change exists.
export const PHASES = [
  { id: 'spec', label: 'Spec', hint: 'spec-author writes intent, delta and ADRs' },
  { id: 'gate1', label: 'Gate 1', hint: 'your review: intent, REQs and ADRs' },
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

export function phasesOf(change: SddChange) {
  if (change.size !== 'fix') return [...PHASES]
  return FIX_ORDER.map(id => PHASES.find(p => p.id === id)!)
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

// Changes grouped by phase (agents ignored, as in byActivity), the most advanced phase first and
// changes without one last. Each group keeps the input's order.
export function byPhase(changes: readonly SddChange[]): [PhaseId | undefined, SddChange[]][] {
  const groups = new Map<PhaseId | undefined, SddChange[]>()
  for (const c of changes) {
    const id = phaseOf(c, [])
    const group = groups.get(id)
    if (group) group.push(c)
    else groups.set(id, [c])
  }
  const at = (id: PhaseId | undefined) => (id === undefined ? -1 : PHASES.findIndex(p => p.id === id))
  return [...groups].sort(([a], [b]) => at(b) - at(a))
}
