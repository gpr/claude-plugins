import { test, expect } from 'claude-code/testing'
import { formatHit, parseOutline, sectionAt } from './kb'

const OUTLINE = `---
source: src/a.py
source_sha256: abc
lines: 40
status: enriched
---
# src/a.py

## L1-2 preamble
- desc: Imports.

## L3-9 def parse(x):
- calls: tokenize · called by: main
- desc: Parses input.

## L11-20 def main():
- desc: _(pending)_
`

test('parseOutline reads frontmatter, sections, graph and descriptions', () => {
  const o = parseOutline(OUTLINE, 'fallback')
  expect(o.source).toBe('src/a.py')
  expect(o.sha).toBe('abc')
  expect(o.sections.map(s => [s.start, s.end])).toEqual([[1, 2], [3, 9], [11, 20]])
  expect(o.sections[1].graph).toBe('calls: tokenize · called by: main')
  expect(o.sections[1].desc).toBe('Parses input.')
  expect(o.sections[2].desc).toBe('')
})

test('sectionAt maps outline lines to sections, none for frontmatter', () => {
  const o = parseOutline(OUTLINE, 'x')
  expect(sectionAt(o, 3)).toBeUndefined() // frontmatter
  const parse = o.sections[1]
  expect(sectionAt(o, parse.line)).toBe(parse) // header line
  expect(sectionAt(o, parse.line + 2)).toBe(parse) // its desc line
})

test('formatHit prints location, description, graph and stale marker', () => {
  const o = parseOutline(OUTLINE, 'x')
  expect(formatHit('src/a.py', o.sections[1], false)).toBe(
    'src/a.py:3-9  def parse(x):  — Parses input.  [calls: tokenize · called by: main]',
  )
  expect(formatHit('src/a.py', o.sections[2], true)).toBe(
    'src/a.py:11-20  def main():  (stale: source changed since outline)',
  )
})
