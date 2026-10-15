// Write-permission rules of the spec-driven workflow, as pure functions.
// register.tsx feeds them the caller's role (from the tool call's agentId) and
// file lookups; tests/guard.test.ts exercises them directly.

export type Cfg = {
  specs_dir: string
  changes_dir: string
  adr_dir: string
  acceptance_dir: string
}

export const DEFAULT_CFG: Cfg = {
  specs_dir: 'specs',
  changes_dir: 'changes',
  adr_dir: 'adr',
  acceptance_dir: 'tests/acceptance',
}

export type Role =
  | 'lead'
  | 'spec-author'
  | 'planner'
  | 'acceptance-tester'
  | 'implementer'
  | 'verifier'
  | 'other'

/** What a status lookup answers: the `status:` of a front matter, or undefined. */
export type Lookup = {
  changeStatus: (change: string) => Promise<string | undefined>
  adrStatus: (relPath: string) => Promise<string | undefined>
}

export const WRITE_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit'])

const ROLES: Role[] = ['spec-author', 'planner', 'acceptance-tester', 'implementer', 'verifier']

/** Agent type as the engine reports it (`sdd:implementer`) to a role. */
export function roleOf(agentType: string | undefined): Role {
  if (agentType === undefined) return 'lead'
  const bare = agentType.startsWith('sdd:') ? agentType.slice(4) : agentType
  return (ROLES as string[]).includes(bare) && agentType.startsWith('sdd:') ? (bare as Role) : 'other'
}

export function cleanCfg(raw: Partial<Cfg> | undefined): Cfg {
  const out = { ...DEFAULT_CFG }
  for (const k of Object.keys(DEFAULT_CFG) as (keyof Cfg)[]) {
    const v = raw?.[k]
    if (typeof v === 'string' && v.trim() !== '') out[k] = v.trim().replace(/^\.\//, '').replace(/\/+$/, '')
  }
  return out
}

/** Normalises a POSIX path: `.` and `..` resolved, repeated slashes folded. */
export function normalize(path: string): string {
  const isAbs = path.startsWith('/')
  const out: string[] = []
  for (const part of path.split('/')) {
    if (part === '' || part === '.') continue
    if (part === '..') {
      if (out.length > 0 && out[out.length - 1] !== '..') out.pop()
      else if (!isAbs) out.push('..')
      continue
    }
    out.push(part)
  }
  return (isAbs ? '/' : '') + out.join('/')
}

/** Path relative to the first base that contains it, with that base; else undefined. */
export function relTo(path: string, bases: string[]): { rel: string; base: string } | undefined {
  for (const raw of bases) {
    const base = normalize(raw)
    const full = normalize(path.startsWith('/') ? path : `${base}/${path}`)
    if (full === base) return { rel: '', base }
    if (full.startsWith(base === '/' ? '/' : `${base}/`)) {
      return { rel: full.slice(base === '/' ? 1 : base.length + 1), base }
    }
  }
  return undefined
}

const under = (rel: string, dir: string) => rel === dir || rel.startsWith(`${dir}/`)

function changeOf(rel: string, cfg: Cfg): string | undefined {
  const parts = rel.split('/')
  const c = cfg.changes_dir.split('/')
  const isIn = c.every((seg, i) => parts[i] === seg)
  return isIn && parts.length > c.length + 1 ? parts[c.length] : undefined
}

/** Deny reason for a file write by `role`, or undefined to allow. */
export async function checkPath(rel: string, role: Role, cfg: Cfg, look: Lookup): Promise<string | undefined> {
  const { specs_dir: S, changes_dir: C, adr_dir: A, acceptance_dir: T } = cfg
  // everyone
  if (under(rel, S)) return `${rel}: living specs change only through \`sdd sync <change>\`.`
  if (under(rel, `${C}/archive`)) return `${rel}: archived changes are immutable.`
  if (under(rel, C) && rel.endsWith('/frozen.json')) return `${rel}: written only by \`sdd freeze\`.`
  if (under(rel, A) && rel !== A) {
    const st = await look.adrStatus(rel)
    if (st === 'accepted' || st === 'superseded' || st === 'deprecated') {
      return `${rel}: this ADR is ${st}. Write a new one with \`sdd adr-new <title> --supersedes ADR-NNNN\`.`
    }
  }
  if (role === 'lead') return undefined
  // every subagent
  if (under(rel, '.claude')) return `${rel}: subagents cannot change workflow configuration.`
  const ch = changeOf(rel, cfg)
  const name = rel.split('/').pop() ?? ''
  const isTopLevelOfChange = ch !== undefined && rel === `${C}/${ch}/${name}`
  const chStatus = async () => (ch ? await look.changeStatus(ch) : undefined)

  switch (role) {
    case 'spec-author': {
      if (under(rel, A)) return undefined
      if (ch && ((isTopLevelOfChange && name === 'intent.md') || under(rel, `${C}/${ch}/specs`))) {
        const st = await chStatus()
        return st === undefined || st === 'draft'
          ? undefined
          : `change ${ch} is ${st}: its spec is frozen. Ask the lead to reopen it.`
      }
      return `${rel}: spec-author writes only intent.md, the spec delta and proposed ADRs.`
    }
    case 'planner': {
      if (isTopLevelOfChange && (name === 'plan.md' || name === 'tasks.md')) {
        const st = await chStatus()
        return st === 'draft' || st === 'approved' ? undefined : `change ${ch} is ${st}: its plan is frozen.`
      }
      return `${rel}: planner writes only plan.md and tasks.md.`
    }
    case 'acceptance-tester':
      if (under(rel, T) || (isTopLevelOfChange && name === 'tasks.md')) return undefined
      return `${rel}: acceptance-tester writes only under ${T}/ and tasks.md.`
    case 'implementer':
      if (under(rel, T)) {
        return `${rel}: acceptance tests are frozen. If one is wrong, stop and report BLOCKED with the REQ id.`
      }
      if (under(rel, A)) return `${rel}: decisions are not changed during implementation. Report BLOCKED.`
      if (under(rel, C) && !(isTopLevelOfChange && name === 'tasks.md')) {
        return `${rel}: the spec is frozen. Report BLOCKED with the REQ id instead.`
      }
      return undefined
    case 'verifier':
      return 'verifier is read-only.'
    default:
      return undefined // other subagents (Explore, general-purpose): the rules above only
  }
}

const WRITE_BASH =
  /(>>?|\btee\b|\bsed\s+-i|\bperl\s+-[a-z]*i|\bmv\b|\bcp\b|\brm\b|\btruncate\b|\bdd\b|\bgit\s+(checkout|restore|rm|mv|apply)\b|\bpatch\b|\binstall\b|write_text|open\([^)]*['"][wa])/

/** Splits a shell command into words (quotes respected, no expansion). */
export function words(cmd: string): string[] {
  const out: string[] = []
  const re = /"((?:[^"\\]|\\.)*)"|'([^']*)'|(\S+)/g
  for (let m = re.exec(cmd); m !== null; m = re.exec(cmd)) out.push(m[1] ?? m[2] ?? m[3] ?? '')
  return out
}

/**
 * Deny reason for a Bash command by `role`, or undefined. Heuristic backstop:
 * `sdd verify-frozen` is the authoritative check for the acceptance tests.
 */
export function checkBash(cmd: string, role: Role, cfg: Cfg, bases: string[]): string | undefined {
  if (role === 'lead') return undefined
  if (/tools\/sdd\.py/.test(cmd)) return 'call the `mcp__sdd__sdd` tool instead of running sdd.py.'
  if (!WRITE_BASH.test(cmd)) return undefined
  const { specs_dir: S, changes_dir: C, adr_dir: A, acceptance_dir: T } = cfg
  for (const raw of words(cmd)) {
    const tok = raw.replace(/^[0-9]*>+/, '')
    if (!tok.includes('/') && !tok.endsWith('.md')) continue
    const hit = relTo(tok, bases)
    if (!hit || hit.rel.startsWith('..')) continue
    const r = hit.rel
    const isProtected = [S, A, '.claude'].some(d => under(r, d))
    if (role === 'implementer' && (under(r, T) || (under(r, C) && !r.endsWith('tasks.md')))) {
      return `Bash write touching ${r} is not allowed for the implementer. Report BLOCKED instead.`
    }
    if (role === 'verifier' && (under(r, T) || under(r, C))) return `verifier is read-only (${r}).`
    if (isProtected) return `Bash write touching ${r} is not allowed for ${role}.`
  }
  return undefined
}

/** Which roles may run each `sdd` subcommand; absent = everyone. */
const SDD_RULES: Record<string, Role[]> = {
  init: ['lead'],
  new: ['lead'],
  'set-status': ['lead'],
  sync: ['lead'],
  'adr-accept': ['lead'],
  freeze: ['lead', 'acceptance-tester'],
  'delta-stub': ['lead', 'spec-author'],
  'adr-new': ['lead', 'spec-author'],
}

export function checkSdd(sub: string | undefined, role: Role): string | undefined {
  if (sub === undefined) return 'give the subcommand as the first element of args, e.g. ["check", "<change>"].'
  const allowed = SDD_RULES[sub]
  if (!allowed || allowed.includes(role)) return undefined
  return `\`sdd ${sub}\` is run by ${allowed.join(' or ')} only, not ${role}.`
}

/** `status:` from a markdown file's front matter. */
export function frontStatus(text: string): string | undefined {
  if (!text.startsWith('---')) return undefined
  const end = text.indexOf('\n---', 3)
  const head = end < 0 ? text : text.slice(0, end)
  return /^status:\s*(\S+)/m.exec(head)?.[1]
}
