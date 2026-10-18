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
  ['draft fix skips the spec', change('draft', [], 'fix'), [], 'plan'],
  ['draft fix with only its test task', change('draft', [task('T1', 'test', false)], 'fix'), [], 'plan'],
  ['draft fix while planner runs', change('draft', [task('T1', 'test', false), task('T2', 'impl', false)], 'fix'), ['planner'], 'plan'],
  ['draft fix, planned, test open', change('draft', [task('T1', 'test', false), task('T2', 'impl', false)], 'fix'), [], 'acceptance'],
  ['draft fix, planned, tester running', change('draft', [task('T1', 'test', true), task('T2', 'impl', false)], 'fix'), ['acceptance-tester'], 'acceptance'],
  ['draft fix, planned and tested', change('draft', [task('T1', 'test', true), task('T2', 'impl', false)], 'fix'), [], 'gate2'],
  ['approved without tasks', change('approved'), [], 'plan'],
  ['approved while planner runs', change('approved', [task('T1', 'test', false)]), ['planner'], 'plan'],
  ['approved with tasks', change('approved', [task('T1', 'test', false)]), [], 'gate2'],
  ['implementing, test task open', change('implementing', [task('T1', 'test', false), task('T2', 'impl', false)]), [], 'acceptance'],
  ['implementing, tests done', change('implementing', [task('T1', 'test', true), task('T2', 'impl', false)]), [], 'implement'],
  ['implementing, all done', change('implementing', [task('T1', 'test', true), task('T2', 'impl', true)]), [], 'verify'],
  ['implementing, all done, verifier running', change('implementing', [task('T1', 'test', true)]), ['verifier'], 'verify'],
  ['verified', change('verified'), [], 'sync'],
  ['unknown status', change('?'), [], undefined],
]

const stored = (phase: string, c: SddChange): SddChange => ({ ...c, phase })

const STORED: [string, SddChange, string[], string | undefined][] = [
  ['stored phase beats derivation (draft would be gate1)', stored('plan', change('draft')), [], 'plan'],
  ['stored phase beats running agents', stored('implement', change('implementing')), ['verifier'], 'implement'],
  ['unknown stored phase falls back', stored('bogus', change('verified')), [], 'sync'],
  ['stored spec on a fix is not a fix phase: derived', { ...stored('spec', change('draft', [], 'fix')) }, [], 'plan'],
  ['stored done has no phase', stored('done', change('archived')), [], undefined],
]

for (const [name, c, running, want] of [...CASES, ...STORED]) {
  test(`phase: ${name}`, () => {
    expect(phaseOf(c, running)).toBe(want)
  })
}

test('a fix lists no spec or Gate 1 step, and its tests come before Gate 2', () => {
  expect(phasesOf(change('draft', [], 'fix')).map(p => p.id)).toEqual(['plan', 'acceptance', 'gate2', 'implement', 'verify', 'sync'])
  expect(phasesOf(change('draft')).length).toBe(8)
})

const named = (id: string, c: SddChange): SddChange => ({ ...c, id })
// a fix at Gate 2 (tests done) and one still in acceptance: Gate 2 comes later in a fix
const fixAtGate2 = named('fix-gate2', change('draft', [task('T1', 'test', true), task('T2', 'impl', false)], 'fix'))
const fixInAcceptance = named('fix-acceptance', change('draft', [task('T1', 'test', false), task('T2', 'impl', false)], 'fix'))

test('stepOf counts in the change\'s own workflow', () => {
  expect(stepOf(fixInAcceptance)).toBe(1)
  expect(stepOf(fixAtGate2)).toBe(2)
  expect(stepOf(change('approved', [task('T1', 'test', false)]))).toBe(3)
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
