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
 * with every character but `[a-zA-Z0-9_-]` folded to `-` (`sdd:planner` -> `sdd-planner`).
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
 * What a write does to a file: its text `before` (undefined: a new file, or unreadable) and
 * `after` (undefined: not computable), and the text it `added` (Write content, Edit new strings).
 */
export type Write = { before?: string; after?: string; added: string }

/** The tool input fields a file write carries. */
export type EditInput = {
  content?: string
  old_string?: string
  new_string?: string
  replace_all?: boolean
  edits?: { old_string?: string; new_string?: string; replace_all?: boolean }[]
}

function replaceIn(text: string, old: unknown, neu: unknown, all: unknown): string | undefined {
  if (typeof old !== 'string' || typeof neu !== 'string' || old === '') return undefined
  if (!text.includes(old)) return text // the tool fails on it: nothing changes
  return all === true ? text.split(old).join(neu) : text.replace(old, () => neu)
}

/** A file's text after a Write, Edit or MultiEdit, as the tool would leave it; undefined if unknown. */
export function applyEdit(before: string | undefined, tool: string, input: EditInput): string | undefined {
  if (tool === 'Write') return input.content
  if (before === undefined) return undefined
  if (tool === 'Edit') return replaceIn(before, input.old_string, input.new_string, input.replace_all)
  if (tool !== 'MultiEdit') return undefined
  let text: string | undefined = before
  for (const e of input.edits ?? []) text = text === undefined ? undefined : replaceIn(text, e.old_string, e.new_string, e.replace_all)
  return text
}

/** Files whose `status:` only `sdd` moves: a change's intent.md and the ADRs. register.tsx reads these before a write. */
export function statusMatters(rel: string, cfg: Cfg): boolean {
  return rel.endsWith('/intent.md') || (under(rel, cfg.adr_dir) && rel.endsWith('.md'))
}

/**
 * Whether a write moves a file's front-matter `status:`. With the text after the write, the statuses
 * before and after are compared: an Edit that splices `draft` into `approved` mid-line counts. A new
 * file may be `draft` or have none. Without it, every `status:` line the write adds must be `current`.
 */
export function statusChanged(w: Write, current: string): boolean {
  if (w.after === undefined) return statusesIn(w.added).some(s => s !== current)
  const after = frontStatus(w.after)
  return w.before === undefined ? after !== undefined && after !== 'draft' : after !== frontStatus(w.before)
}

/**
 * Deny reason for a file write by `role`, or undefined to allow. `write` describes what the write
 * does to the file, used to keep `status:` changes in `sdd`.
 */
export async function checkPath(
  rel: string,
  role: Role,
  cfg: Cfg,
  look: Lookup,
  write?: Write,
): Promise<string | undefined> {
  const { specs_dir: S, changes_dir: C, adr_dir: A, acceptance_dir: T } = cfg
  // everyone (the repo's concept templates aside: the lead may adapt them)
  if (under(rel, `${S}/.templates`) || under(rel, `${A}/.templates`)) {
    return role === 'lead' ? undefined : `${rel}: concept templates are changed by the lead only.`
  }
  if (under(rel, S)) return `${rel}: living specs change only through \`sdd sync <change>\`.`
  if (under(rel, `${C}/archive`)) return `${rel}: archived changes are immutable.`
  if (under(rel, C) && rel.endsWith('/frozen.json')) return `${rel}: written only by \`sdd freeze\`.`
  if (under(rel, C) && rel.endsWith('/state.json')) {
    return `${rel}: written only by \`sdd start\`, \`checkpoint\`, \`set-pr\`, \`requires\`, \`freeze\` and \`finish\`.`
  }
  const adrGenerated = rel === `${A}/index.md` || rel === `${A}/log.md`
  if (adrGenerated && role !== 'lead') return `${rel}: generated by \`sdd\` (adr-new, adr-accept, bundle --fix).`
  const isAdr = under(rel, A) && rel !== A && !adrGenerated
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
  if (write !== undefined) {
    if (isAdr && statusChanged(write, adrSt ?? 'draft')) {
      return `${rel}: ADR status changes only through \`sdd adr-accept\` (lead).`
    }
    if (isTopLevelOfChange && name === 'intent.md' && statusChanged(write, (await chStatus()) ?? 'draft')) {
      return `${rel}: change status moves only through \`sdd set-status\` (lead).`
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
  /(>>?|\btee\b|\bsed\s+-i|\bperl\s+-[a-z]*i|\bmv\b|\bcp\b|\brm\b|\btouch\b|\bln\b|\bmkdir\b|\brmdir\b|\btruncate\b|\bdd\b|\bgit\s+(checkout|restore|rm|mv|apply)\b|\bpatch\b|\binstall\b|write_text|open\([^)]*['"][wa])/

/** fd duplications and /dev/null sinks (`2>&1`, `>/dev/null`): redirects that write no file. */
const FD_REDIRECT = /[0-9]*>&[0-9]*-?|[0-9]*>>?\s*\/dev\/null\b/g

/** Splits a shell command into words (quotes respected, no expansion). */
export function words(cmd: string): string[] {
  const out: string[] = []
  const re = /"((?:[^"\\]|\\.)*)"|'([^']*)'|(\S+)/g
  for (let m = re.exec(cmd); m !== null; m = re.exec(cmd)) out.push(m[1] ?? m[2] ?? m[3] ?? '')
  return out
}

/** Splits a shell command at `;`, `&&`, `||`, `|`, `&` and newlines outside quotes. */
export function segments(cmd: string): string[] {
  const out: string[] = []
  let cur = ''
  let quote: string | undefined
  for (let i = 0; i < cmd.length; i++) {
    const c = cmd[i]
    if (quote !== undefined) {
      cur += c
      if (c === quote && !(quote === '"' && cmd[i - 1] === '\\')) quote = undefined
    } else if (c === '"' || c === "'") {
      quote = c
      cur += c
    } else if (c === ';' || c === '\n' || c === '|' || (c === '&' && cmd[i + 1] !== '>' && cmd[i - 1] !== '>')) {
      out.push(cur)
      cur = ''
      if ((c === '&' || c === '|') && cmd[i + 1] === c) i++
    } else {
      cur += c
    }
  }
  out.push(cur)
  return out.map(x => x.trim()).filter(x => x !== '')
}

/** A redirect into a file (`> f`, `>>f`, `x>f`, `&> f`), its target captured. */
const REDIRECT = /&?>>?\|?\s*(?:"((?:[^"\\]|\\.)*)"|'([^']*)'|([^\s;&|<>()]+))/g

/** Commands whose operands are the files they write: every one counts for the read-only verifier. */
const WRITE_COMMANDS = new Set(['tee', 'touch', 'cp', 'mv', 'rm', 'truncate', 'install', 'ln', 'mkdir', 'rmdir'])

/**
 * Deny reason for a Bash command by `role`, or undefined. Heuristic backstop on the command text:
 * `sdd verify-frozen` is the authoritative check for the acceptance tests. Each segment is checked
 * on its own, from the directory earlier `cd`s moved to; a writing segment's candidate paths are its
 * words with a `/` or ending in `.md`, its redirect targets, all its arguments once a `cd` moved
 * away from the cwd, and, for the verifier, the operands of file-writing commands.
 */
export function checkBash(cmd: string, role: Role, cfg: Cfg, bases: string[]): string | undefined {
  if (role === 'lead') return undefined
  if (/tools\/sdd\.py/.test(cmd)) return 'call the `mcp__sdd__sdd` tool instead of running sdd.py.'
  const { specs_dir: S, changes_dir: C, adr_dir: A, acceptance_dir: T } = cfg
  const start = normalize(bases[0] ?? '/')
  let dir = start
  for (const seg of segments(cmd.replace(FD_REDIRECT, ''))) {
    const ws = words(seg)
    const head = (ws[0] ?? '').replace(/^\(+/, '')
    if (head === 'cd' || head === 'pushd') {
      const to = ws[1]
      // `cd`, `cd -`, `cd ~/x`, `cd $X`: somewhere this check cannot follow, so back to the cwd
      dir = to === undefined || /^[-~$]/.test(to) ? start : to.startsWith('/') ? normalize(to) : normalize(`${dir}/${to}`)
      continue
    }
    const targets = [...seg.matchAll(REDIRECT)].map(m => m[1] ?? m[2] ?? m[3] ?? '')
    // what the segment writes besides its redirects (`pytest tests > /tmp/log` writes only /tmp/log)
    const rest = seg.replace(REDIRECT, ' ')
    const writes = WRITE_BASH.test(rest)
    if (!writes && targets.length === 0) continue
    const restWords = words(rest)
    const args = restWords.slice(1).filter(w => !w.startsWith('-'))
    const candidates = [
      ...targets,
      ...(writes ? restWords.filter(w => w.includes('/') || w.endsWith('.md')) : []),
      ...(writes && dir !== start ? args : []),
      ...(writes && role === 'verifier' && (WRITE_COMMANDS.has(head.split('/').pop() ?? '') || head === 'sed') ? args : []),
    ]
    for (const tok of candidates) {
      if (tok === '') continue
      const hit = relTo(tok.startsWith('/') ? tok : `${dir}/${tok}`, bases)
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
  freeze: ['lead'],
  'baseline-tree': ['lead', 'verifier'],
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
