import { expect, test } from 'claude-code/testing'

import { activeOf, byActivity, byStatus, phaseOf, phasesOf, stepOf } from '../hooks/phase'
import type { SddChange, SddTask } from '../types'

const task = (id: string, kind: SddTask['kind'], done: boolean): SddTask => ({ id, kind, done, refs: ['capabilities/a#AC-01'] })
const change = (status: string, tasks: SddTask[] = [], size = 'change'): SddChange => ({
  id: 'c1',
  title: 'c1',
  status,
  size,
  adrs: [],
  tasks,
})

const CASES: [string, SddChange, string[], string | undefined][] = [
  ['draft while spec-author runs', change('draft'), ['spec-author'], 'spec'],
  ['draft, nobody running: waits on the user', change('draft'), [], 'gate1'],
  ['draft while contract-designer runs', change('draft'), ['contract-designer'], 'contract'],
  ['draft, surface declared, no contract files yet', { ...change('draft'), surface: ['api'] }, [], 'contract'],
  ['draft, surface declared, contracts written: Gate 1', { ...change('draft'), surface: ['api'], contracts: true }, [], 'gate1'],
  ['draft baseline with a surface: no contract step', { ...change('draft'), size: 'baseline', surface: ['api'] }, [], 'gate1'],
  ['draft, surface none: Gate 1', { ...change('draft'), surface: [] }, [], 'gate1'],
  ['draft fix skips the spec', change('draft', [], 'fix'), [], 'plan'],
  ['draft fix with only its test task', change('draft', [task('T1', 'test', false)], 'fix'), [], 'plan'],
  ['draft fix while planner runs', change('draft', [task('T1', 'test', false), task('T2', 'impl', false)], 'fix'), ['planner'], 'plan'],
  ['draft fix, planned, test open', change('draft', [task('T1', 'test', false), task('T2', 'impl', false)], 'fix'), [], 'acceptance'],
  ['draft fix, planned, tester running', change('draft', [task('T1', 'test', true), task('T2', 'impl', false)], 'fix'), ['acceptance-tester'], 'acceptance'],
  ['draft fix with a delta, spec-author running', { ...change('draft', [], 'fix'), delta: true }, ['spec-author'], 'spec'],
  ['draft fix with a delta, written: its Gate 1', { ...change('draft', [], 'fix'), delta: true }, [], 'gate1'],
  ['draft fix, planned and tested', change('draft', [task('T1', 'test', true), task('T2', 'impl', false)], 'fix'), [], 'gate2'],
  ['approved without tasks', change('approved'), [], 'plan'],
  ['approved while planner runs', change('approved', [task('T1', 'test', false)]), ['planner'], 'plan'],
  ['approved with tasks', change('approved', [task('T1', 'test', false)]), [], 'gate2'],
  ['implementing, test task open', change('implementing', [task('T1', 'test', false), task('T2', 'impl', false)]), [], 'acceptance'],
  ['implementing, tests done', change('implementing', [task('T1', 'test', true), task('T2', 'impl', false)]), [], 'implement'],
  ['implementing, all done', change('implementing', [task('T1', 'test', true), task('T2', 'impl', true)]), [], 'verify'],
  ['implementing, all done, verifier running', change('implementing', [task('T1', 'test', true)]), ['verifier'], 'verify'],
  ['baseline, tests done: nothing to implement', change('implementing', [task('T1', 'test', true)], 'baseline'), [], 'verify'],
  ['baseline, test open', change('implementing', [task('T1', 'test', false)], 'baseline'), [], 'acceptance'],
  ['baseline, chore open: still no Implement step', change('implementing', [task('T1', 'test', true), task('T2', 'chore', false)], 'baseline'), [], 'verify'],
  ['verified', change('verified'), [], 'sync'],
  ['unknown status', change('?'), [], undefined],
]

const stored = (phase: string, c: SddChange): SddChange => ({ ...c, phase })

const STORED: [string, SddChange, string[], string | undefined][] = [
  ['stored phase beats derivation (draft would be gate1)', stored('plan', change('draft')), [], 'plan'],
  ['stored phase beats running agents', stored('implement', change('implementing')), ['verifier'], 'implement'],
  ['unknown stored phase falls back', stored('bogus', change('verified')), [], 'sync'],
  ['stored spec on a fix: it adds a criterion first', stored('spec', change('draft', [], 'fix')), [], 'spec'],
  ['stored acceptance on a fix is kept', stored('acceptance', change('draft', [task('T1', 'test', false)], 'fix')), [], 'acceptance'],
  ['stored implement on a baseline is not a baseline phase: derived', stored('implement', change('implementing', [task('T1', 'test', true)], 'baseline')), [], 'verify'],
  ['stored done has no phase', stored('done', change('archived')), [], undefined],
]

for (const [name, c, running, want] of [...CASES, ...STORED]) {
  test(`phase: ${name}`, () => {
    expect(phaseOf(c, running)).toBe(want)
  })
}

test('a fix lists no spec or Gate 1 step, and its tests come before Gate 2', () => {
  expect(phasesOf(change('draft', [], 'fix')).map(p => p.id)).toEqual(['plan', 'acceptance', 'gate2', 'implement', 'verify', 'sync'])
  expect(phasesOf(change('draft')).length).toBe(9)
})

test('a change lists the Contract step unless its surface is none', () => {
  expect(phasesOf(change('draft')).map(p => p.id).slice(0, 3)).toEqual(['spec', 'contract', 'gate1'])
  expect(phasesOf({ ...change('draft'), surface: ['cli'] }).map(p => p.id)).toContain('contract')
  expect(phasesOf({ ...change('draft'), surface: [] }).map(p => p.id)).not.toContain('contract')
  expect(phasesOf({ ...change('draft'), surface: null }).map(p => p.id)).toContain('contract')
})

test('a fix that adds a criterion lists Spec and Gate 1 first', () => {
  const ids = ['spec', 'gate1', 'plan', 'acceptance', 'gate2', 'implement', 'verify', 'sync']
  expect(phasesOf({ ...change('draft', [], 'fix'), delta: true }).map(p => p.id)).toEqual(ids)
  expect(phasesOf(stored('gate1', change('draft', [], 'fix'))).map(p => p.id)).toEqual(ids)
})

test('a baseline lists no Implement step', () => {
  expect(phasesOf(change('draft', [], 'baseline')).map(p => p.id)).toEqual(['spec', 'gate1', 'plan', 'gate2', 'acceptance', 'verify', 'sync'])
})

const named = (id: string, c: SddChange): SddChange => ({ ...c, id })
// a fix at Gate 2 (tests done) and one still in acceptance: Gate 2 comes later in a fix
const fixAtGate2 = named('fix-gate2', change('draft', [task('T1', 'test', true), task('T2', 'impl', false)], 'fix'))
const fixInAcceptance = named('fix-acceptance', change('draft', [task('T1', 'test', false), task('T2', 'impl', false)], 'fix'))

test('stepOf counts in the change\'s own workflow', () => {
  expect(stepOf(fixInAcceptance)).toBe(1)
  expect(stepOf(fixAtGate2)).toBe(2)
  expect(stepOf(change('approved', [task('T1', 'test', false)]))).toBe(4)
  expect(stepOf(change('?'))).toBe(-1)
})

test('byActivity: status first, then the furthest in its own workflow, then the most tasks', () => {
  const unplanned = named('unplanned', change('approved'))
  const planned = named('planned', change('approved', [task('T1', 'test', false)]))
  const bigger = named('bigger', change('approved', [task('T1', 'test', false), task('T2', 'impl', false)]))
  const building = named('building', change('implementing', [task('T1', 'test', false)]))
  expect(byActivity([unplanned, planned, bigger, building]).map(c => c.id)).toEqual(['building', 'bigger', 'planned', 'unplanned'])
  expect(byActivity([fixInAcceptance, fixAtGate2]).map(c => c.id)).toEqual(['fix-gate2', 'fix-acceptance'])
})

test('byStatus groups work in progress first, unknown statuses last', () => {
  const groups = byStatus([
    named('a', change('approved')),
    named('b', change('verified')),
    named('c', change('?')),
    named('d', change('approved')),
    named('e', change('implementing')),
    named('f', change('draft')),
  ])
  expect(groups.map(([s, cs]) => [s, cs.map(c => c.id)])).toEqual([
    ['implementing', ['e']],
    ['verified', ['b']],
    ['approved', ['a', 'd']],
    ['draft', ['f']],
    ['?', ['c']],
  ])
})

test('activeOf: the change on the checked-out branch, else the first', () => {
  const a = named('a', change('implementing'))
  const b = { ...named('b', change('draft')), branch: 'sdd/b' }
  expect(activeOf([a, b], 'sdd/b')?.id).toBe('b')
  expect(activeOf([a, b], 'main')?.id).toBe('a')
  expect(activeOf([a, b], '')?.id).toBe('a')
  expect(activeOf([], 'sdd/b')).toBeUndefined()
})
