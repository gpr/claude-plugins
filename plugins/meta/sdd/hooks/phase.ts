import type { SddChange } from '../types'

// The workflow phases of skills/change, in order. Triage happens before a change exists.
export const PHASES = [
  { id: 'spec', label: 'Spec', hint: 'spec-author writes intent, delta and ADRs' },
  { id: 'gate1', label: 'Gate 1', hint: 'your review: intent, REQs and ADRs' },
  { id: 'plan', label: 'Plan', hint: 'planner writes plan.md and tasks.md' },
  { id: 'gate2', label: 'Gate 2', hint: 'sdd check, then set implementing' },
  { id: 'acceptance', label: 'Acceptance tests', hint: 'acceptance-tester writes failing tests, then freeze' },
  { id: 'implement', label: 'Implement', hint: 'implementers make the frozen tests pass' },
  { id: 'verify', label: 'Verify', hint: 'verifier runs the suites and reviews the diff' },
  { id: 'sync', label: 'Sync', hint: 'sdd sync merges the delta into specs/ and archives' },
] as const

export type PhaseId = (typeof PHASES)[number]['id']

// A fix has no spec delta: it starts at its test task.
const FIX_SKIPS: ReadonlySet<PhaseId> = new Set(['spec', 'gate1'])

export function phasesOf(change: SddChange) {
  return change.size === 'fix' ? PHASES.filter(p => !FIX_SKIPS.has(p.id)) : [...PHASES]
}

// Derived from the change's status, its tasks and the workflow agents running (types
// without the `sdd:` prefix). Agents are session-wide, so they only refine within a status.
export function phaseOf(change: SddChange, running: readonly string[]): PhaseId | undefined {
  const isRunning = (type: string) => running.includes(type)
  const open = (kind: string) => change.tasks.some(t => t.kind === kind && !t.done)
  switch (change.status) {
    case 'draft':
      // A fix starts with the lead's test task and goes from draft to implementing at
      // Gate 2: it is planned once the planner has added its impl tasks.
      if (change.size === 'fix') return isRunning('planner') || !change.tasks.some(t => t.kind === 'impl') ? 'plan' : 'gate2'
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
