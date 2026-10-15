import { expect, test } from 'claude-code/testing'

import { phaseOf, phasesOf } from '../hooks/phase'
import type { SddChange, SddTask } from '../types'

const task = (id: string, kind: SddTask['kind'], done: boolean): SddTask => ({ id, kind, done, reqs: ['REQ-A-001'] })
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
  ['draft fix, planned', change('draft', [task('T1', 'test', false), task('T2', 'impl', false)], 'fix'), [], 'gate2'],
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

for (const [name, c, running, want] of CASES) {
  test(`phase: ${name}`, () => {
    expect(phaseOf(c, running)).toBe(want)
  })
}

test('a fix lists no spec or Gate 1 step', () => {
  expect(phasesOf(change('draft', [], 'fix')).map(p => p.id)).toEqual(['plan', 'gate2', 'acceptance', 'implement', 'verify', 'sync'])
  expect(phasesOf(change('draft')).length).toBe(8)
})
