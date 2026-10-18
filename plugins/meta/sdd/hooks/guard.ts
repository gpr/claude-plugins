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
  adr_dir: 'adrs',
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

/** ADR statuses that lock the file: OKF's stable/deprecated, and accepted/superseded of the
 * ADRs written before the OKF templates (a repo that has not migrated them yet). */
const DECIDED = new Set(['stable', 'deprecated', 'accepted', 'superseded'])

export const WRITE_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit'])

const ROLES: Role[] = ['spec-author', 'planner', 'acceptance-tester', 'implementer', 'verifier']

/** Agent type as the engine reports it (`sdd:implementer`) to a role. */
export function roleOf(agentType: string | undefined): Role {
  if (agentType === undefined) return 'lead'
  if (!agentType.startsWith('sdd:')) return 'other'
  const bare = agentType.slice(4)
  return (ROLES as string[]).includes(bare) ? (bare as Role) : 'other'
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
  // A relative path is resolved once, against the first base (the cwd), as the shell would.
  const full = normalize(path.startsWith('/') || bases.length === 0 ? path : `${bases[0]}/${path}`)
  for (const raw of bases) {
    const base = normalize(raw)
    if (full === base) return { rel: '', base }
    if (full.startsWith(base === '/' ? '/' : `${base}/`)) {
      return { rel: full.slice(base === '/' ? 1 : base.length + 1), base }
    }
  }
  return undefined
}

const under = (rel: string, dir: string) => rel === dir || rel.startsWith(`${dir}/`)

/**
 * A workflow agent's own `memory:` directories. Claude Code names them after the agent type
 * with non-alphanumerics folded to `-` (`sdd:planner` -> `sdd-planner`).
 */
export function memoryDirs(role: Role): string[] {
  return [`.claude/agent-memory/sdd-${role}`, `.claude/agent-memory-local/sdd-${role}`]
}

function changeOf(rel: string, cfg: Cfg): string | undefined {
  const parts = rel.split('/')
  const c = cfg.changes_dir.split('/')
  const isIn = c.every((seg, i) => parts[i] === seg)
  return isIn && parts.length > c.length + 1 ? parts[c.length] : undefined
}

/** `status:` values a write would put at the start of a line (front matter). */
export function statusesIn(text: string): string[] {
  return [...text.matchAll(/^status:[ \t]*(\S*)/gm)].map(m => unquote(m[1] ?? ''))
}

/** A YAML scalar without its quotes: `"stable"` and `'stable'` read as `stable`, as sdd.py reads them. */
export function unquote(v: string): string {
  return v.length >= 2 && (v[0] === '"' || v[0] === "'") && v[v.length - 1] === v[0] ? v.slice(1, -1) : v
}

/**
 * Deny reason for a file write by `role`, or undefined to allow. `written` is the text the
 * write adds (Write content, Edit new strings), used to keep `status:` changes in `sdd`.
 */
export async function checkPath(
  rel: string,
  role: Role,
  cfg: Cfg,
  look: Lookup,
  written?: string,
): Promise<string | undefined> {
  const { specs_dir: S, changes_dir: C, adr_dir: A, acceptance_dir: T } = cfg
  // everyone (the repo's concept templates aside: the lead may adapt them)
  if (under(rel, `${S}/.templates`)) {
    return role === 'lead' ? undefined : `${rel}: concept templates are changed by the lead only.`
  }
  if (under(rel, S)) return `${rel}: living specs change only through \`sdd sync <change>\`.`
  if (under(rel, `${C}/archive`)) return `${rel}: archived changes are immutable.`
  if (under(rel, C) && rel.endsWith('/frozen.json')) return `${rel}: written only by \`sdd freeze\`.`
  if (under(rel, C) && rel.endsWith('/state.json')) return `${rel}: written only by \`sdd start\`, \`checkpoint\`, \`set-pr\` and \`finish\`.`
  const isAdr = under(rel, A) && rel !== A
  const adrSt = isAdr ? await look.adrStatus(rel) : undefined
  if (adrSt !== undefined && DECIDED.has(adrSt)) {
    return `${rel}: this ADR is ${adrSt} (decided). Write a new one with \`sdd adr-new <title> --supersedes ADR-NNNN\`.`
  }
  if (role === 'lead') return undefined
  // every subagent
  if (role !== 'other' && memoryDirs(role).some(d => under(rel, d))) return undefined
  if (under(rel, '.claude')) return `${rel}: subagents cannot change workflow configuration.`
  const ch = changeOf(rel, cfg)
  const name = rel.split('/').pop() ?? ''
  const isTopLevelOfChange = ch !== undefined && rel === `${C}/${ch}/${name}`
  const chStatus = async () => (ch ? await look.changeStatus(ch) : undefined)
  if (written !== undefined) {
    if (isAdr && statusesIn(written).some(s => s !== (adrSt ?? 'draft'))) {
      return `${rel}: ADR status changes only through \`sdd adr-accept\` (lead).`
    }
    if (isTopLevelOfChange && name === 'intent.md') {
      const st = (await chStatus()) ?? 'draft'
      if (statusesIn(written).some(s => s !== st)) {
        return `${rel}: change status moves only through \`sdd set-status\` (lead).`
      }
    }
  }

  switch (role) {
    case 'spec-author': {
      if (under(rel, A)) return undefined
      if (ch && ((isTopLevelOfChange && name === 'intent.md') || under(rel, `${C}/${ch}/specs`))) {
        const st = await chStatus()
        return st === undefined || st === 'draft'
          ? undefined
          : `change ${ch} is ${st}: its spec is frozen. Ask the lead to reopen it.`
      }
      return `${rel}: spec-author writes only intent.md, the spec delta and draft ADRs.`
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
        return `${rel}: acceptance tests are frozen. If one is wrong, stop and report BLOCKED with its id (capabilities/<id>#AC-NN or invariants/<id>).`
      }
      if (under(rel, A)) return `${rel}: decisions are not changed during implementation. Report BLOCKED.`
      if (under(rel, C) && !(isTopLevelOfChange && name === 'tasks.md')) {
        return `${rel}: the spec is frozen. Report BLOCKED with the criterion or invariant id instead.`
      }
      return undefined
    case 'verifier':
      return 'verifier is read-only (its memory directory aside).'
    default:
      return undefined // other subagents (Explore, general-purpose): the rules above only
  }
}

const WRITE_BASH =
  /(>>?|\btee\b|\bsed\s+-i|\bperl\s+-[a-z]*i|\bmv\b|\bcp\b|\brm\b|\btruncate\b|\bdd\b|\bgit\s+(checkout|restore|rm|mv|apply)\b|\bpatch\b|\binstall\b|write_text|open\([^)]*['"][wa])/

/** fd duplications and /dev/null sinks (`2>&1`, `>/dev/null`): redirects that write no file. */
const FD_REDIRECT = /[0-9]*>&[0-9]*-?|[0-9]*>>?\s*\/dev\/null\b/g

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
  if (!WRITE_BASH.test(cmd.replace(FD_REDIRECT, ''))) return undefined
  const { specs_dir: S, changes_dir: C, adr_dir: A, acceptance_dir: T } = cfg
  for (const raw of words(cmd)) {
    const tok = raw.replace(/^[0-9]*>+/, '')
    if (!tok.includes('/') && !tok.endsWith('.md')) continue
    const hit = relTo(tok, bases)
    if (!hit || hit.rel.startsWith('..')) continue
    const r = hit.rel
    const isProtected =
      [S, A, '.claude', `${C}/archive`].some(d => under(r, d)) || (under(r, C) && (r.endsWith('/frozen.json') || r.endsWith('/state.json')))
    if (role === 'verifier') return `verifier is read-only (${r}).`
    if (role === 'implementer' && (under(r, T) || (under(r, C) && !r.endsWith('tasks.md')))) {
      return `Bash write touching ${r} is not allowed for the implementer. Report BLOCKED instead.`
    }
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
  start: ['lead'],
  checkpoint: ['lead'],
  'set-pr': ['lead'],
  requires: ['lead'],
  resume: ['lead'],
  finish: ['lead'],
  freeze: ['lead', 'acceptance-tester'],
  'delta-new': ['lead', 'spec-author'],
  'delta-stub': ['lead', 'spec-author'],
  'adr-new': ['lead', 'spec-author'],
}

export function checkSdd(sub: string | undefined, role: Role): string | undefined {
  if (sub === undefined) return 'give the subcommand as the first element of args, e.g. ["check", "<change>"].'
  const allowed = SDD_RULES[sub]
  if (!allowed || allowed.includes(role)) return undefined
  return `\`sdd ${sub}\` is run by ${allowed.join(' or ')} only, not ${role}.`
}

/**
 * Deny reason for the `bundle` tool, or undefined. Checking is open to every role. `--fix` on
 * the living `specs` and `adrs` bundles is lead-only (only the lead's call may write them); on a
 * change it is open to the lead and the spec-author: it only touches front matter and the
 * generated indexes, never the text of a criterion or an invariant.
 */
export function checkBundle(target: string | undefined, fix: boolean, role: Role): string | undefined {
  if (target === undefined || target === '') return 'give the target: "specs", "adrs" or a change id.'
  if (!fix) return undefined
  if (target === 'specs' || target === 'adrs') {
    return role === 'lead' ? undefined : `\`bundle ${target} --fix\` is run by the lead only, not ${role}.`
  }
  return role === 'lead' || role === 'spec-author' ? undefined : `\`bundle ${target} --fix\` is run by lead or spec-author only, not ${role}.`
}

/** `status:` from a markdown file's front matter. */
export function frontStatus(text: string): string | undefined {
  if (!text.startsWith('---')) return undefined
  const end = text.indexOf('\n---', 3)
  const head = end < 0 ? text : text.slice(0, end)
  const v = /^status:[ \t]*(\S+)/m.exec(head)?.[1]
  return v === undefined ? undefined : unquote(v)
}
