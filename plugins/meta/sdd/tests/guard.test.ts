import { describe, expect, test } from 'claude-code/testing'

import { checkBash, checkBundle, checkPath, checkSdd, cleanCfg, DEFAULT_CFG, frontStatus, relTo, roleOf, statusesIn } from '../hooks/guard'
import type { Lookup, Role } from '../hooks/guard'

const ROOT = '/repo'
const STATUS: Record<string, string> = {
  'changes/c1/intent.md': 'draft',
  'changes/c2/intent.md': 'implementing',
  'adrs/0001_x.md': 'stable',
  'adrs/0002_y.md': 'draft',
  'adrs/0004_w.md': 'deprecated',
  'adr/ADR-0005-old.md': 'accepted',
  'adr/ADR-0006-older.md': 'superseded',
}
const look: Lookup = {
  changeStatus: async ch => STATUS[`changes/${ch}/intent.md`],
  adrStatus: async rel => STATUS[rel],
}

async function decide(role: Role, path: string) {
  const hit = relTo(path, [ROOT])
  if (!hit) return role === 'lead' ? 'allow' : 'deny'
  return (await checkPath(hit.rel, role, DEFAULT_CFG, look)) === undefined ? 'allow' : 'deny'
}

const bash = (role: Role, cmd: string) => (checkBash(cmd, role, DEFAULT_CFG, [ROOT]) === undefined ? 'allow' : 'deny')

const FILE_CASES: [Role, string, 'allow' | 'deny'][] = [
  ['lead', 'specs/capabilities/auth.md', 'deny'],
  ['lead', 'src/app.py', 'allow'],
  ['lead', 'adrs/0001_x.md', 'deny'],
  ['lead', 'adrs/0002_y.md', 'allow'],
  ['lead', 'adrs/0004_w.md', 'deny'],
  ['lead', 'specs/.templates/capability.md.tmpl', 'allow'],
  ['spec-author', 'specs/.templates/capability.md.tmpl', 'deny'],
  ['implementer', 'specs/.templates/capability.md.tmpl', 'deny'],
  ['lead', 'changes/c1/frozen.json', 'deny'],
  ['lead', 'changes/c1/state.json', 'deny'],
  ['planner', 'changes/c1/state.json', 'deny'],
  ['lead', 'changes/archive/2026-01-01-c0/intent.md', 'deny'],
  ['lead', '.claude/sdd.json', 'allow'],
  ['spec-author', 'changes/c1/specs/capabilities/auth.md', 'allow'],
  ['spec-author', 'changes/c1/intent.md', 'allow'],
  ['spec-author', 'changes/c2/specs/capabilities/auth.md', 'deny'],
  ['spec-author', 'adrs/0003_z.md', 'allow'],
  ['spec-author', 'src/app.py', 'deny'],
  ['spec-author', 'changes/c1/plan.md', 'deny'],
  ['planner', 'changes/c1/plan.md', 'allow'],
  ['planner', 'changes/c2/tasks.md', 'deny'],
  ['planner', 'changes/c1/specs/capabilities/auth.md', 'deny'],
  ['acceptance-tester', 'tests/acceptance/test_a.py', 'allow'],
  ['acceptance-tester', 'changes/c2/tasks.md', 'allow'],
  ['acceptance-tester', 'src/app.py', 'deny'],
  ['implementer', 'src/app.py', 'allow'],
  ['implementer', 'tests/acceptance/test_a.py', 'deny'],
  ['implementer', 'tests/acceptance/../acceptance/test_a.py', 'deny'],
  ['implementer', 'changes/c2/tasks.md', 'allow'],
  ['implementer', 'changes/c2/specs/capabilities/auth.md', 'deny'],
  ['implementer', '.claude/settings.json', 'deny'],
  ['verifier', 'src/app.py', 'deny'],
  ['verifier', '.claude/agent-memory/sdd-verifier/MEMORY.md', 'allow'],
  ['verifier', '.claude/agent-memory/sdd-implementer/MEMORY.md', 'deny'],
  ['implementer', '.claude/agent-memory/sdd-implementer/notes.md', 'allow'],
  ['implementer', '.claude/agent-memory-local/sdd-implementer/MEMORY.md', 'allow'],
  ['implementer', '.claude/agent-memory/sdd-implementer/../../settings.json', 'deny'],
  ['acceptance-tester', '.claude/agent-memory/sdd-implementer/MEMORY.md', 'deny'],
  ['spec-author', '.claude/agent-memory/sdd-spec-author/MEMORY.md', 'allow'],
  ['planner', '.claude/agent-memory/sdd-planner/MEMORY.md', 'allow'],
  ['other', '.claude/agent-memory/sdd-other/MEMORY.md', 'deny'],
  ['other', 'src/app.py', 'allow'],
  ['other', 'specs/auth/spec.md', 'deny'],
]

describe('file writes', () => {
  for (const [role, rel, want] of FILE_CASES) {
    test(`${role} ${rel} -> ${want}`, async () => {
      expect(await decide(role, `${ROOT}/${rel}`)).toBe(want)
    })
  }
  test('a subagent writing outside the project is refused', async () => {
    expect(await decide('implementer', '/etc/passwd')).toBe('deny')
  })
})

describe('bash', () => {
  test('tests may run', () => expect(bash('implementer', 'pytest -q tests/acceptance')).toBe('allow'))
  test('sed -i on an acceptance test is refused', () =>
    expect(bash('implementer', "sed -i 's/assert/#/' tests/acceptance/test_a.py")).toBe('deny'))
  test('redirect into an acceptance test is refused', () =>
    expect(bash('implementer', 'echo pass > tests/acceptance/test_a.py')).toBe('deny'))
  test('copying over source is fine', () => expect(bash('implementer', 'cp new.py src/app.py')).toBe('allow'))
  test('running sdd.py directly is refused for subagents', () =>
    expect(bash('planner', 'python3 /x/tools/sdd.py check c1')).toBe('deny'))
  test('the lead is not checked', () => expect(bash('lead', 'rm -rf specs')).toBe('allow'))
  test('verifier cannot write into changes', () => expect(bash('verifier', 'echo x >> changes/c2/tasks.md')).toBe('deny'))
  test('verifier cannot write source either', () => expect(bash('verifier', 'rm src/app.py')).toBe('deny'))
  test('stderr redirects are not writes', () => {
    expect(bash('implementer', 'pytest -q tests/acceptance/test_a.py 2>&1 | tail -20')).toBe('allow')
    expect(bash('verifier', 'pytest -q tests/acceptance 2>/dev/null')).toBe('allow')
  })
  test('state.json is protected from Bash writes too', () => {
    expect(bash('implementer', 'echo {} > changes/c1/state.json')).toBe('deny')
  })
  test('frozen.json and the archive are protected for every subagent', () => {
    expect(bash('acceptance-tester', 'echo {} > changes/c1/frozen.json')).toBe('deny')
    expect(bash('planner', 'rm -rf changes/archive/2026-01-01-c0')).toBe('deny')
  })
  test('a relative path is resolved against the cwd once', () =>
    expect(checkBash("sed -i 's/a/b/' ../tests/acceptance/test_a.py", 'implementer', DEFAULT_CFG, [`${ROOT}/src`, ROOT])).toBeDefined())
})

describe('status changes stay in sdd', () => {
  const write = (role: Role, rel: string, text: string) => checkPath(rel, role, DEFAULT_CFG, look, text)
  test('spec-author cannot approve its own change', async () => {
    expect(await write('spec-author', 'changes/c1/intent.md', 'status: approved')).toBeDefined()
    expect(await write('spec-author', 'changes/c1/intent.md', '---\nstatus: draft\n---\n# x')).toBeUndefined()
  })
  test('spec-author cannot accept its own ADR', async () => {
    expect(await write('spec-author', 'adrs/0002_y.md', 'status: stable')).toBeDefined()
    expect(await write('spec-author', 'adrs/0003_z.md', '---\nstatus: draft\n---')).toBeUndefined()
  })
  test('the lead may still edit status by hand', async () =>
    expect(await write('lead', 'changes/c1/intent.md', 'status: approved')).toBeUndefined())
})

describe('sdd subcommands', () => {
  test('sync is lead-only', () => {
    expect(checkSdd('sync', 'implementer')).toBeDefined()
    expect(checkSdd('sync', 'lead')).toBeUndefined()
  })
  test('freeze: acceptance-tester yes, implementer no', () => {
    expect(checkSdd('freeze', 'acceptance-tester')).toBeUndefined()
    expect(checkSdd('freeze', 'implementer')).toBeDefined()
  })
  test('delta-new: spec-author yes, implementer no', () => {
    expect(checkSdd('delta-new', 'spec-author')).toBeUndefined()
    expect(checkSdd('delta-new', 'implementer')).toBeDefined()
  })
  test('check and context are open to everyone', () => {
    expect(checkSdd('check', 'verifier')).toBeUndefined()
    expect(checkSdd('context', 'implementer')).toBeUndefined()
  })
  test('branch, PR and resume subcommands are lead-only', () => {
    for (const sub of ['start', 'checkpoint', 'set-pr', 'requires', 'resume', 'finish']) {
      expect(checkSdd(sub, 'lead')).toBeUndefined()
      expect(checkSdd(sub, 'implementer')).toBeDefined()
    }
  })
  test('deps is read-only for every role', () => expect(checkSdd('deps', 'implementer')).toBeUndefined())
  test('missing subcommand is refused', () => expect(checkSdd(undefined, 'lead')).toBeDefined())
})

describe('roles', () => {
  test('plugin agent types map to roles', () => {
    expect(roleOf('sdd:implementer')).toBe('implementer')
    expect(roleOf(undefined)).toBe('lead')
    expect(roleOf('Explore')).toBe('other')
    expect(roleOf('implementer')).toBe('other')
    expect(roleOf('sdd:unknown')).toBe('other')
  })
})

describe('bundle tool', () => {
  test('checking is open to every role', () => {
    for (const role of ['lead', 'spec-author', 'planner', 'implementer', 'verifier'] as const) {
      expect(checkBundle('specs', false, role)).toBeUndefined()
      expect(checkBundle('c1', false, role)).toBeUndefined()
    }
  })
  test('fixing the living specs is lead-only', () => {
    expect(checkBundle('specs', true, 'lead')).toBeUndefined()
    expect(checkBundle('specs', true, 'spec-author')).toBeDefined()
    expect(checkBundle('specs', true, 'implementer')).toBeDefined()
    expect(checkBundle('adrs', true, 'lead')).toBeUndefined()
    expect(checkBundle('adrs', true, 'spec-author')).toBeDefined()
  })
  test('fixing a change is for the lead and the spec-author', () => {
    expect(checkBundle('c1', true, 'lead')).toBeUndefined()
    expect(checkBundle('c1', true, 'spec-author')).toBeUndefined()
    expect(checkBundle('c1', true, 'planner')).toBeDefined()
    expect(checkBundle('c1', true, 'verifier')).toBeDefined()
  })
  test('a missing target is refused', () => {
    expect(checkBundle(undefined, false, 'lead')).toBeDefined()
    expect(checkBundle('', true, 'lead')).toBeDefined()
  })
})

describe('bundle files stay generated', () => {
  const write = (role: Role, rel: string) => checkPath(rel, role, DEFAULT_CFG, look, 'x')
  test('nobody but sdd writes the specs bundle or a change index', async () => {
    expect(await write('lead', 'specs/capabilities/index.md')).toBeDefined()
    expect(await write('lead', 'specs/invariants/no_secrets.md')).toBeDefined()
    for (const role of ['spec-author', 'planner', 'implementer'] as const) {
      expect(await write(role, 'changes/c1/index.md')).toBeDefined()
    }
  })
  test('spec-author writes deltas in capability and invariant directories', async () => {
    expect(await write('spec-author', 'changes/c1/specs/capabilities/auth/tokens.md')).toBeUndefined()
    expect(await write('spec-author', 'changes/c1/specs/invariants/no_secrets.md')).toBeUndefined()
  })
})

describe('quoted statuses read as sdd.py reads them', () => {
  test('frontStatus drops YAML quotes', () => {
    expect(frontStatus('---\nstatus: "stable"\n---\n')).toBe('stable')
    expect(frontStatus("---\nstatus: 'deprecated'\n---\n")).toBe('deprecated')
    expect(frontStatus('---\nstatus: draft\n---\n')).toBe('draft')
  })
  test('a quoted status in a write is the same status', async () => {
    expect(statusesIn('status: "draft"')).toEqual(['draft'])
    expect(await checkPath('adrs/0002_y.md', 'spec-author', DEFAULT_CFG, look, '---\nstatus: "draft"\n---')).toBeUndefined()
  })
})

describe('ADRs decided before the OKF templates stay locked', () => {
  const legacy = cleanCfg({ adr_dir: 'adr' })
  test('accepted and superseded are refused, proposed is not', async () => {
    expect(await checkPath('adr/ADR-0005-old.md', 'lead', legacy, look)).toBeDefined()
    expect(await checkPath('adr/ADR-0006-older.md', 'lead', legacy, look)).toBeDefined()
    expect(await checkPath('adr/ADR-0007-new.md', 'lead', legacy, look)).toBeUndefined()
  })
})
